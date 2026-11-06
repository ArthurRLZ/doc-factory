"""Relatório de risco de privacidade de um lote — para o encarregado de dados (DPO) decidir antes de compartilhar.

Responde, com números e evidência: "este lote tem 340 CPFs (212 pessoas), 12 documentos com dados de saúde".

Como funciona (tudo determinístico: sem modelo/LLM, o mesmo lote dá sempre o mesmo relatório):
  - Identificadores (CPF, RG, nome, endereço, CEP, e-mail, telefone): contados pelos marcadores que a
    anonimização já deixa no texto guardado ("[CPF]", "[NOME]"...). Não precisa reprocessar nada e funciona
    em lotes antigos.
  - Pessoas distintas: impressões digitais de CPF válido (dígito verificador conferido) que o pipeline já
    guarda em Pagina.sinais["cpfs"]. O CPF em si nunca é lido nem exibido aqui.
  - Dados sensíveis (art. 5º, II da LGPD): pelo TIPO do documento (ASO é sempre saúde) e por um léxico de termos.
    Termos genéricos exigem mais de um acerto (uma palavra solta, como "exame", não basta).

É uma triagem por heurística, não um parecer jurídico: o relatório diz o MÍNIMO detectado e mostra a evidência.
"""
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Documento, Lote, Pagina
from app.pipeline.classificar import normalizar
from app.status import StatusRevisao
from app.tipos import nome_tipo

# --------------------------------------------------------------- identificadores (marcadores da anonimização)
# Mantenha em sincronia com os rótulos de app/pipeline/anonimizar.py (um teste confere isso).
PESSOAIS = {"CPF": "CPF", "RG": "RG", "NOME": "Nome de pessoa", "ENDERECO": "Endereço", "CEP": "CEP",
            "EMAIL": "E-mail", "TELEFONE": "Telefone"}
EMPRESA = {"CNPJ": "CNPJ (empresa; pode ser dado pessoal em MEI/empresário individual)"}
RX_MARCADOR = re.compile(r"\[(" + "|".join([*PESSOAIS, *EMPRESA]) + r")\]")

# --------------------------------------------------------------- dados sensíveis (LGPD, art. 5º, II)
# minimo = quantos termos DIFERENTES precisam aparecer para marcar o documento.
# tipos  = tipos de documento que já indicam a categoria por si só (ver tipos.py).
SENSIVEIS: dict[str, dict] = {
    "SAUDE": {
        "nome": "Dados de saúde",
        "minimo": 2,
        "tipos": {"ASO"},
        "termos": ["atestado de saude", "atestado medico", "laudo medico", "diagnostico", "prontuario",
                   "internacao", "cirurgia", "medico do trabalho", "medico examinador", "exame admissional",
                   "exame periodico", "exame demissional", "exame de retorno", "pcmso", "receita medica",
                   "cid-10", "cid 10", "hiv", "crm", "inapto", "afastamento medico", "licenca medica"],
    },
    "BIOMETRIA": {
        "nome": "Dados biométricos",
        "minimo": 1,
        "tipos": set(),
        "termos": ["impressao digital", "biometria", "biometrico", "reconhecimento facial", "polegar direito"],
    },
    "SINDICAL": {
        "nome": "Filiação sindical",
        "minimo": 1,
        "tipos": set(),
        "termos": ["contribuicao sindical", "mensalidade sindical", "desconto sindical", "filiacao sindical",
                   "filiado ao sindicato", "filiada ao sindicato"],
    },
}
for _c in SENSIVEIS.values():
    _c["rx"] = re.compile(r"\b(" + "|".join(re.escape(t) for t in _c["termos"]) + r")\b")

AVISO = ("Triagem automática por padrões e palavras-chave; não substitui a avaliação do encarregado de dados "
         "nem é parecer jurídico. Os números são o MÍNIMO detectado.")


# --------------------------------------------------------------- análise de um documento (funções puras)
@dataclass
class AnaliseDocumento:
    marcadores: Counter = field(default_factory=Counter)             # {"CPF": 3, "NOME": 5, ...}
    sensiveis: dict[str, list[str]] = field(default_factory=dict)    # {"SAUDE": ["tipo do documento: ASO", ...]}

    @property
    def tem_pessoais(self) -> bool:
        return any(self.marcadores.get(r) for r in PESSOAIS)


def analisar_documento(tipo: str, texto: str | None) -> AnaliseDocumento:
    """Conta identificadores e procura dados sensíveis em UM documento (texto já anonimizado)."""
    texto = texto or ""
    analise = AnaliseDocumento(marcadores=Counter(RX_MARCADOR.findall(texto)))
    normal = normalizar(texto)
    for chave, cat in SENSIVEIS.items():
        evidencias: list[str] = []
        if tipo in cat["tipos"]:
            evidencias.append(f"tipo do documento: {tipo}")
        achados = list(dict.fromkeys(cat["rx"].findall(normal)))      # termos diferentes, na ordem em que aparecem
        if len(achados) >= cat["minimo"]:
            evidencias += achados
        if evidencias:
            analise.sensiveis[chave] = evidencias[:6]
    return analise


# --------------------------------------------------------------- nível de risco e recomendações
def nivel_de_risco(docs_sensiveis: int, docs_pessoais: int) -> tuple[str, list[str]]:
    """alto: tem dado sensível · medio: só identificadores diretos · baixo: nenhum dos dois."""
    if docs_sensiveis:
        return "alto", [f"{docs_sensiveis} documento(s) com dados pessoais sensíveis (art. 5º, II da LGPD)"]
    if docs_pessoais:
        return "medio", [f"{docs_pessoais} documento(s) com identificadores diretos (CPF, RG, nome, endereço...)"]
    return "baixo", ["nenhum dado pessoal detectado"]


def _frase_resumo(ocorrencias: Counter, pessoas: int, sensiveis_docs: Counter, total_docs: int) -> str:
    partes = []
    if ocorrencias["CPF"]:
        partes.append(f"{ocorrencias['CPF']} CPF(s)" + (f" ({pessoas} pessoa(s) distinta(s))" if pessoas else ""))
    for rotulo, frase in (("RG", "RG(s)"), ("NOME", "nome(s) de pessoa"), ("ENDERECO", "endereço(s)"),
                          ("EMAIL", "e-mail(s)"), ("TELEFONE", "telefone(s)")):
        if ocorrencias[rotulo]:
            partes.append(f"{ocorrencias[rotulo]} {frase}")
    for chave, n in sensiveis_docs.items():
        partes.append(f"{n} documento(s) com {SENSIVEIS[chave]['nome'].lower()}")
    if not partes:
        return f"Este lote ({total_docs} documento(s)) não tem dados pessoais detectados."
    return f"Este lote ({total_docs} documento(s)) tem " + ", ".join(partes) + "."


def _recomendacoes(lote_id: str, nivel: str, pessoas: int, pendentes: int, sensiveis: bool) -> list[str]:
    r = [f"Compartilhe a versão anonimizada (GET /lotes/{lote_id}/zip?anonimizado=true), nunca os PDFs originais."]
    if sensiveis:
        r.append("Dado sensível exige base legal específica (LGPD, art. 11): confirme-a antes de compartilhar.")
    if pessoas:
        r.append(f"{pessoas} pessoa(s) identificada(s): confirme que o compartilhamento é necessário para a "
                 "finalidade (princípio da necessidade, LGPD art. 6º, III).")
    if pendentes:
        r.append(f"{pendentes} documento(s) ainda estão na fila de revisão: o relatório pode mudar depois dela.")
    r.append("Confira os PDFs antes de compartilhar: dados que a detecção ou o OCR não reconheceram podem continuar visíveis.")
    return r


# --------------------------------------------------------------- relatório do lote
def relatorio_do_lote(db: Session, lote: Lote, limite: int = 100) -> dict:
    docs = db.execute(
        select(Documento.id, Documento.ordem, Documento.tipo, Documento.pagina_inicio,
               Documento.pagina_fim, Documento.status_revisao, Documento.texto)
        .where(Documento.lote_id == lote.id).order_by(Documento.ordem)).all()

    # pessoas distintas: impressões digitais de CPF válido (nunca o CPF)
    pessoas: set[str] = set()
    for sinais in db.scalars(select(Pagina.sinais).where(Pagina.lote_id == lote.id)):
        pessoas.update(c["h"] for c in (sinais or {}).get("cpfs", []))

    ocorrencias: Counter = Counter()
    docs_com: Counter = Counter()                            # rótulo → nº de documentos que têm
    sensiveis_docs: Counter = Counter()                      # categoria → nº de documentos
    sensiveis_tipos: dict[str, Counter] = {k: Counter() for k in SENSIVEIS}
    sensiveis_termos: dict[str, Counter] = {k: Counter() for k in SENSIVEIS}
    detalhe, docs_pessoais, pendentes = [], 0, 0

    for d in docs:
        a = analisar_documento(d.tipo, d.texto)
        ocorrencias.update(a.marcadores)
        docs_com.update(r for r, n in a.marcadores.items() if n)
        docs_pessoais += a.tem_pessoais
        pendentes += d.status_revisao == StatusRevisao.PENDENTE
        for chave, evid in a.sensiveis.items():
            sensiveis_docs[chave] += 1
            sensiveis_tipos[chave][d.tipo] += 1
            sensiveis_termos[chave].update(e for e in evid if not e.startswith("tipo do documento"))
        if a.sensiveis:
            detalhe.append({"documento_id": d.id, "ordem": d.ordem, "tipo": d.tipo, "tipo_nome": nome_tipo(d.tipo),
                            "titulo": f"Documento {d.ordem + 1}", "pagina_inicio": d.pagina_inicio, "pagina_fim": d.pagina_fim,
                            "categorias": list(a.sensiveis), "evidencias": a.sensiveis})

    nivel, motivos = nivel_de_risco(sum(1 for _ in detalhe), docs_pessoais)
    return {
        "lote_id": lote.id, "lote": f"Lote {lote.id}", "gerado_em": datetime.now(timezone.utc).isoformat(),
        "nivel_risco": nivel, "motivos": motivos,
        "resumo": _frase_resumo(ocorrencias, len(pessoas), sensiveis_docs, len(docs)),
        "totais": {"paginas": lote.total_paginas, "documentos": len(docs),
                   "documentos_com_dados_pessoais": docs_pessoais,
                   "documentos_com_dados_sensiveis": len(detalhe),
                   "pessoas_distintas": len(pessoas), "documentos_em_revisao": pendentes},
        "identificadores": {
            rotulo: {"nome": nome, "ocorrencias": ocorrencias[rotulo], "documentos": docs_com[rotulo]}
            | ({"pessoas_distintas": len(pessoas)} if rotulo == "CPF" else {})
            for rotulo, nome in {**PESSOAIS, **EMPRESA}.items()},
        "dados_sensiveis": {
            chave: {"nome": SENSIVEIS[chave]["nome"], "documentos": sensiveis_docs[chave],
                    "por_tipo": dict(sensiveis_tipos[chave].most_common()),
                    "termos_mais_frequentes": [t for t, _ in sensiveis_termos[chave].most_common(5)]}
            for chave in SENSIVEIS},
        "documentos_sensiveis": detalhe[:limite],
        "documentos_sensiveis_truncado": len(detalhe) > limite,
        "deteccao": {"nomes": settings.ANONIMIZAR_NOMES, "enderecos": settings.ANONIMIZAR_ENDERECOS},
        "recomendacoes": _recomendacoes(lote.id, nivel, len(pessoas), pendentes, bool(detalhe)),
        "aviso": AVISO,
    }
