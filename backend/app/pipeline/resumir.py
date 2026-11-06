"""Etapa 6 — Resumo e prioridade de cada documento.

Roda depois que o documento foi montado (e de novo quando o revisor divide, junta ou troca o tipo).

  com modelo:  o modelo recebe SÓ o texto já anonimizado do documento inteiro.
               Documento grande → resumo em partes + consolidação (ver llm/openai_compat.py).
  sem modelo (ou se ele falhar): resumo "simples" — título, nº de páginas, datas e valores
               encontrados no texto. Nada é inventado; resumo_origem diz de onde veio.

Prioridade do documento = a maior entre: prioridade do tipo, a sugerida pelo modelo e, se o lote
foi enviado como "alta", a do lote.
"""
import logging
import re

from app.config import settings
from app.llm import obter_llm
from app.models import Documento, Lote
from app.pipeline import validade
from app.tipos import (DESCONHECIDO, PRIORIDADE_NOME, PRIORIDADES, campos_do_tipo,
                       nome_tipo, prioridade_do_tipo)

log = logging.getLogger(__name__)

_RX_DATA = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
# milhar com ponto ou espaço: o OCR às vezes lê "1.200,00" como "1 200,00"
_RX_VALOR = re.compile(r"R\$\s?\d{1,3}(?:[. ]\d{3})*(?:,\d{2})?")
_RX_MARCADOR = re.compile(r"^\[(CPF|CNPJ|RG|EMAIL|TELEFONE|NOME|ENDERECO|CEP)\]")


def _unicos(itens: list[str], limite: int = 5) -> list[str]:
    vistos = []
    for i in itens:
        if i not in vistos:
            vistos.append(i)
    return vistos[:limite]


def _titulo(texto: str) -> str | None:
    """Primeira linha com cara de título (curta, com letras, sem ser só um marcador)."""
    for linha in (texto or "").splitlines():
        linha = linha.strip()
        if 6 <= len(linha) <= 90 and re.search(r"[A-Za-zÀ-ú]{3}", linha) and not _RX_MARCADOR.match(linha):
            return linha
    return None


def resumo_simples(tipo: str, texto: str, n_paginas: int) -> tuple[str, dict]:
    datas = _unicos(_RX_DATA.findall(texto or ""))
    valores = _unicos(_RX_VALOR.findall(texto or ""))
    partes = [f"{nome_tipo(tipo)} com {n_paginas} página{'s' if n_paginas != 1 else ''}."]
    titulo = _titulo(texto)
    if titulo:
        partes.append(f"Título: “{titulo}”.")
    if datas:
        partes.append(f"Datas encontradas: {', '.join(datas)}.")
    if valores:
        partes.append(f"Valores encontrados: {', '.join(valores)}.")
    return " ".join(partes), {"titulo": titulo, "datas": datas, "valores": valores}


def calcular_prioridade(tipo: str, prioridade_lote: int, sugerida: str | None,
                        motivo_modelo: str = "", status_validade: str | None = None,
                        dias: int | None = None) -> tuple[int, str]:
    candidatos = [(prioridade_do_tipo(tipo),
                   "tipo não identificado" if tipo == DESCONHECIDO else f"prioridade padrão de {nome_tipo(tipo)}")]
    if prioridade_lote == PRIORIDADES["alta"]:      # lote urgente puxa todos os seus documentos para alta
        candidatos.append((prioridade_lote, "prioridade do lote"))
    if sugerida in PRIORIDADES:
        candidatos.append((PRIORIDADES[sugerida], f"modelo: {motivo_modelo}" if motivo_modelo else "sugerida pelo modelo"))
    if status_validade == "vencido":                # documento vencido sempre exige ação
        candidatos.append((PRIORIDADES["alta"], f"documento vencido há {abs(dias or 0)} dia(s)"))
    elif status_validade == "vencendo":
        candidatos.append((PRIORIDADES["alta"], f"vence em {dias} dia(s)"))
    # no empate de valor, o motivo mais específico (o último adicionado) explica melhor
    melhor = max(c[0] for c in candidatos)
    return melhor, [m for v, m in candidatos if v == melhor][-1]


def _aplicar_validade(doc: Documento, sugestao_modelo: dict | None) -> tuple[str, int | None]:
    v = validade.avaliar(doc.tipo, doc.texto or "", sugestao_modelo)
    doc.validade_data, doc.validade_inicio = v.data, v.inicio
    doc.validade_origem, doc.validade_evidencia = v.origem, v.evidencia
    if v.motivos:
        doc.motivos = list(dict.fromkeys((doc.motivos or []) + v.motivos))   # sem duplicar
        if doc.status_revisao == "auto_aprovado":     # o que o revisor já aprovou continua aprovado
            doc.status_revisao = "pendente"
    return validade.status(doc.validade_data, doc.tipo)


def resumir_documento(lote: Lote, doc: Documento) -> None:
    """Preenche título, resumo, campos, validade (com evidência) e prioridade do documento."""
    n_paginas = doc.pagina_fim - doc.pagina_inicio + 1
    doc.titulo = (_titulo(doc.texto or "") or nome_tipo(doc.tipo))[:200]
    resp = None
    if settings.RESUMO_ATIVO:
        llm = obter_llm()
        if llm and (doc.texto or "").strip():
            resp = llm.resumir(nome_tipo(doc.tipo), campos_do_tipo(doc.tipo), doc.texto)

    status_v, dias = _aplicar_validade(doc, resp.validade if resp else None)
    manual = doc.prioridade_manual          # prioridade definida pelo revisor não é sobrescrita
    if resp:
        doc.resumo, doc.campos, doc.resumo_origem = resp.resumo, resp.campos, "modelo"
        if not manual:
            doc.prioridade, doc.prioridade_motivo = calcular_prioridade(doc.tipo, lote.prioridade, resp.prioridade,
                                                                        resp.motivo_prioridade, status_v, dias)
    else:
        if settings.RESUMO_ATIVO:
            doc.resumo, doc.campos = resumo_simples(doc.tipo, doc.texto or "", n_paginas)
            doc.resumo_origem = "simples"
        if not manual:
            doc.prioridade, doc.prioridade_motivo = calcular_prioridade(doc.tipo, lote.prioridade, None,
                                                                        status_validade=status_v, dias=dias)


def nome_prioridade(valor: int | None) -> str:
    return PRIORIDADE_NOME.get(valor or 2, "media")
