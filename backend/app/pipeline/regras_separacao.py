"""Regras de separação escritas em português ("mantenha o contrato inteiro junto").

Por que vocabulário fechado: o texto do usuário (ou a resposta da IA) vira SEMPRE uma destas 4 regras, com tipos
que existem em TIPOS — a segmentação nunca executa nada que não esteja aqui, e a regra é auditável.
  {"op": "manter_junto",       "tipos": ["CONTRATO"]}
  {"op": "separar_por_pagina", "tipos": ["GUIA_FGTS"]}
  {"op": "anexar_ao_anterior", "tipos": ["COMPROVANTE_RESIDENCIA"]}
  {"op": "branco_nao_separa"}
A IA interpreta a frase quando está configurada; sem IA (ou se ela falhar) vale o fallback por palavras-chave.
"""
import logging
import re

from app.pipeline.classificar import normalizar
from app.tipos import TIPOS, nome_tipo

log = logging.getLogger(__name__)

OPS = {"manter_junto", "separar_por_pagina", "anexar_ao_anterior", "branco_nao_separa"}
OPS_SEM_TIPO = {"branco_nao_separa"}
NOME_OP = {"manter_junto": "Manter junto", "separar_por_pagina": "Separar cada página",
           "anexar_ao_anterior": "Anexar ao documento anterior", "branco_nao_separa": "Página em branco não separa"}

# Apelidos (sem acento, minúsculos) → chave de tipo. Além disto, o nome de cada tipo (nome_tipo) também vale.
# Ordem importa: o mais específico primeiro ("guia do fgts" antes de "fgts"; "certidao negativa federal" antes de "cnd").
APELIDOS: list[tuple[str, str]] = [
    ("guia do fgts", "GUIA_FGTS"), ("guia fgts", "GUIA_FGTS"), ("guias do fgts", "GUIA_FGTS"),
    ("certificado de regularidade", "CRF_FGTS"), ("crf", "CRF_FGTS"),
    ("cndt", "CNDT"), ("certidao negativa federal", "CND_FEDERAL"), ("cnd", "CND_FEDERAL"),
    ("atestado de saude", "ASO"), ("aso", "ASO"),
    ("carteira de trabalho", "CTPS"), ("ctps", "CTPS"),
    ("ficha de epi", "FICHA_EPI"), ("epi", "FICHA_EPI"),
    ("certificado de nr", "CERTIFICADO_NR"), ("nr-10", "CERTIFICADO_NR"), ("nr 35", "CERTIFICADO_NR"),
    ("treinamento", "CERTIFICADO_NR"),
    ("contracheque", "CONTRACHEQUE"), ("holerite", "CONTRACHEQUE"),
    ("comprovante de residencia", "COMPROVANTE_RESIDENCIA"),
    ("identidade", "IDENTIDADE"), ("rg", "IDENTIDADE"), ("cnh", "IDENTIDADE"),
    ("nota fiscal", "NOTA_FISCAL"), ("nf", "NOTA_FISCAL"),
    ("contrato", "CONTRATO"),
]

EXEMPLOS = ["mantenha o contrato inteiro junto", "cada guia do FGTS é um documento separado",
            "página em branco não separa documentos", "o comprovante de residência fica junto do documento anterior"]

_RX_BRANCO = re.compile(r"(em branco|branca).*(nao|nunca).*(separ|divid|fech)|ignore.*(em branco|branca)")
_RX_SEPARAR = re.compile(r"separad[oa]s?|um por pagina|cada .* (e|eh) um|separe cada")
_RX_JUNTO = re.compile(r"junto|inteiro|completo|nao separe|nao divida|mantenha|manter|unico documento")
_RX_ANEXAR = re.compile(r"anexe|anexar|junto ao anterior|mesmo documento do anterior|fica junto")


def validar(bruto) -> list[dict]:
    """Mantém só regras do vocabulário, com tipos existentes, sem duplicatas. Nunca levanta exceção."""
    saida: list[dict] = []
    for item in bruto if isinstance(bruto, list) else []:
        if not isinstance(item, dict) or item.get("op") not in OPS:
            continue
        op = item["op"]
        if op in OPS_SEM_TIPO:
            regra = {"op": op}
        else:
            tipos = item.get("tipos") if isinstance(item.get("tipos"), list) else []
            tipos = list(dict.fromkeys(t for t in tipos if isinstance(t, str) and t in TIPOS))
            if not tipos:
                continue
            regra = {"op": op, "tipos": tipos}
        if regra not in saida:
            saida.append(regra)
    return saida


def _tipos_citados(frase: str) -> list[str]:
    achados: list[tuple[int, str]] = []
    resto = frase
    candidatos = APELIDOS + [(normalizar(nome_tipo(k)), k) for k in TIPOS]
    for apelido, chave in sorted(candidatos, key=lambda a: -len(a[0])):     # o mais longo primeiro
        m = re.search(rf"\b{re.escape(apelido)}\b", resto)
        if m:
            achados.append((m.start(), chave))
            resto = resto[:m.start()] + " " * len(apelido) + resto[m.end():]   # não casa de novo num pedaço menor
    return list(dict.fromkeys(k for _, k in sorted(achados)))


def interpretar_por_palavras(texto: str) -> list[dict]:
    """Fallback determinístico (sem IA): uma frase por vez, separadas por '.', ';' ou quebra de linha."""
    regras: list[dict] = []
    for frase in re.split(r"[.;\n]+", normalizar(texto or "")):
        frase = frase.strip()
        if not frase:
            continue
        if _RX_BRANCO.search(frase):
            regras.append({"op": "branco_nao_separa"})
            continue
        tipos = _tipos_citados(frase)
        if not tipos:
            continue
        if _RX_ANEXAR.search(frase) and "anterior" in frase:
            regras.append({"op": "anexar_ao_anterior", "tipos": tipos})
        elif _RX_SEPARAR.search(frase):
            regras.append({"op": "separar_por_pagina", "tipos": tipos})
        elif _RX_JUNTO.search(frase):
            regras.append({"op": "manter_junto", "tipos": tipos})
    return validar(regras)


def interpretar(texto: str, llm) -> tuple[list[dict], str]:
    """Tenta a IA (se configurada); resposta vazia, inválida ou erro → palavras-chave.
    Retorna (regras, "ia" | "palavras_chave"). Não há lote aqui: esta chamada não entra no contador por lote."""
    fn = getattr(llm, "interpretar_regras_separacao", None) if llm else None
    if fn:
        try:
            regras = validar(fn(texto, {k: v["nome"] for k, v in TIPOS.items()}))
            if regras:
                return regras, "ia"
        except Exception:
            log.exception("IA falhou ao interpretar a regra; usando palavras-chave")
    return interpretar_por_palavras(texto), "palavras_chave"


def descrever(regra: dict) -> str:
    """'Manter junto: Contrato' (para a tela)."""
    nome = NOME_OP[regra["op"]]
    if regra["op"] in OPS_SEM_TIPO:
        return nome
    return f"{nome}: " + ", ".join(nome_tipo(t) for t in regra["tipos"])
