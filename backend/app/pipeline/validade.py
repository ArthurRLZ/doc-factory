"""Validade / vigência de cada documento — com a evidência de onde veio.

Ordem de decisão (a primeira que encontrar ganha):
  1. TEXTO   — data escrita: "Válida até 15/03/2027", "Validade: 01/10 a 31/10/2026",
               "vigência de 12 (doze) meses a partir de 05/11/2026" (calcula o fim)
  2. MODELO  — o modelo lê o documento e devolve a data + o trecho literal que a comprova.
               Se o trecho NÃO existir no texto, a resposta é descartada (o modelo não pode inventar).
               Se texto e modelo discordarem, o documento vai para revisão.
  3. REGRA   — regra do tipo (tipos.py) a partir da data de emissão/exame/conclusão: ASO + 12 meses,
               CRF + 30 dias, NR-10 + 24 meses...
  4. NADA    — tipos sem validade (CTPS, ficha de EPI...) ou validade não identificada
               (nos tipos em que ela é obrigatória, vai para revisão).

O status (vigente / vencendo / vencido) NÃO é guardado: é calculado na leitura com a data de hoje.
"""
import calendar
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta

from app import util
from app.config import settings
from app.tipos import TIPOS_COM_VALIDADE, TIPOS_VALIDADE_OBRIGATORIA, regra_validade

log = logging.getLogger(__name__)

_MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7,
          "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
_DATA = (r"(?:\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}"
         r"|\d{1,2}\s+de\s+(?:janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"
         r"\s+de\s+\d{4})")

RX_VALIDADE = re.compile(
    rf"(?i)(?:v[aá]lid[ao]s?\s+at[eé]|data\s+de\s+validade|validade|v[aá]lid[ao]\s+por\s+at[eé])\s*[:\-]?\s*"
    rf"(?P<d1>{_DATA})(?:\s*(?:a|at[eé]|-|–)\s*(?P<d2>{_DATA}))?")
RX_VIGENCIA = re.compile(
    rf"(?i)(?:vig[eê]ncia|prazo)\s+(?:de|ser[aá]\s+de|ter[aá]\s+dura[cç][aã]o\s+de)\s+(?P<n>\d{{1,3}})\s*(?:\([^)]{{0,30}}\))?\s*"
    rf"(?P<unid>dias|meses|m[eê]s|anos?)\s+(?:a\s+partir\s+de|contad[oa]s?\s+(?:a\s+partir\s+)?de|desde)\s+(?P<ini>{_DATA})")
RX_DATA_BASE = re.compile(
    rf"(?i)(?:data\s+do\s+exame|data\s+de\s+conclus[aã]o|conclu[ií]d[oa]\s+em|emitid[ao]\s+em|expedi[cç][aã]o|"
    rf"data\s+de\s+emiss[aã]o|realizad[oa]\s+em|data\s+de\s+entrega)\s*[:\-]?\s*(?P<d>{_DATA})")
RX_NR = re.compile(r"(?i)\bNR[\s\-]?(\d{1,2})\b|norma\s+regulamentadora\s+(?:n[º°o]\.?\s*)?(\d{1,2})")


@dataclass
class Validade:
    data: date | None = None
    inicio: date | None = None
    origem: str | None = None         # texto | modelo | regra
    evidencia: str | None = None
    motivos: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ utilitários
def parse_data(s: str | None) -> date | None:
    if not s:
        return None
    s = s.strip().lower()
    m = re.fullmatch(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})", s)
    try:
        if m:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        m = re.fullmatch(r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", s)
        if m and m.group(2) in _MESES:
            return date(int(m.group(3)), _MESES[m.group(2)], int(m.group(1)))
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)          # ISO, caso o modelo devolva assim
        if m:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    return None


def somar(d: date, meses: int = 0, dias: int = 0) -> date:
    if meses:
        mes = d.month - 1 + meses
        ano, mes = d.year + mes // 12, mes % 12 + 1
        d = d.replace(year=ano, month=mes, day=min(d.day, calendar.monthrange(ano, mes)[1]))
    return d + timedelta(days=dias)


def _linha(texto: str, ini: int, fim: int) -> str:
    """O trecho que comprova: a linha inteira onde a data foi achada."""
    a = texto.rfind("\n", 0, ini) + 1
    b = texto.find("\n", fim)
    return texto[a: b if b != -1 else len(texto)].strip()[:300]


def _normalizar(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def evidencia_no_texto(evidencia: str | None, texto: str) -> bool:
    """A frase que o modelo citou existe mesmo no documento? (ignora acento, caixa e espaços)"""
    ev = _normalizar(evidencia or "")
    return len(ev) >= 8 and ev in _normalizar(texto)


# ------------------------------------------------------------------ 1. texto
def validade_no_texto(texto: str) -> Validade | None:
    texto = texto or ""
    m = RX_VALIDADE.search(texto)
    if m:
        fim = parse_data(m.group("d2") or m.group("d1"))
        ini = parse_data(m.group("d1")) if m.group("d2") else None
        if fim:
            return Validade(fim, ini, "texto", _linha(texto, m.start(), m.end()))
    m = RX_VIGENCIA.search(texto)
    if m:
        ini = parse_data(m.group("ini"))
        if ini:
            n, unid = int(m.group("n")), m.group("unid").lower()
            if unid.startswith("dia"):
                fim = somar(ini, dias=n)
            elif unid.startswith("ano"):
                fim = somar(ini, meses=12 * n)
            else:
                fim = somar(ini, meses=n)
            return Validade(fim, ini, "texto", _linha(texto, m.start(), m.end()))
    return None


# ------------------------------------------------------------------ 3. regra do tipo
def validade_por_regra(tipo: str, texto: str) -> Validade | None:
    regra = regra_validade(tipo)
    if not regra:
        return None
    m = RX_DATA_BASE.search(texto or "")
    base = parse_data(m.group("d")) if m else None
    if not base:
        return None
    meses, dias, detalhe = regra.get("meses", 0), regra.get("dias", 0), ""
    if "por_nr" in regra:
        nr = RX_NR.search(texto or "")
        numero = nr and (nr.group(1) or nr.group(2))
        if numero and numero.lstrip("0") in regra["por_nr"]:
            meses, detalhe = regra["por_nr"][numero.lstrip("0")], f"NR-{numero.lstrip('0')}: "
    prazo = f"{meses} meses" if meses else f"{dias} dias"
    return Validade(somar(base, meses=meses, dias=dias), base, "regra",
                    f"{_linha(texto, m.start(), m.end())}  →  regra: {detalhe}validade de {prazo}")


# ------------------------------------------------------------------ decisão
def avaliar(tipo: str, texto: str, sugestao_modelo: dict | None = None) -> Validade:
    """sugestao_modelo: {"data": "dd/mm/aaaa", "inicio": ..., "evidencia": "trecho literal"} ou None."""
    if tipo not in TIPOS_COM_VALIDADE:
        return Validade()

    pelo_texto = validade_no_texto(texto)

    pelo_modelo = None
    if sugestao_modelo and sugestao_modelo.get("data"):
        data_m = parse_data(str(sugestao_modelo.get("data")))
        if data_m and evidencia_no_texto(sugestao_modelo.get("evidencia"), texto):
            pelo_modelo = Validade(data_m, parse_data(str(sugestao_modelo.get("inicio") or "")), "modelo",
                                   str(sugestao_modelo.get("evidencia"))[:300])
        elif data_m:
            log.info("validade do modelo descartada: evidência não encontrada no texto")

    if pelo_texto:
        if pelo_modelo and abs((pelo_modelo.data - pelo_texto.data).days) > 1:
            pelo_texto.motivos.append(f"datas de validade divergentes: texto {pelo_texto.data:%d/%m/%Y}, "
                                      f"modelo {pelo_modelo.data:%d/%m/%Y}")
        return pelo_texto
    if pelo_modelo:
        return pelo_modelo
    pela_regra = validade_por_regra(tipo, texto)
    if pela_regra:
        return pela_regra
    v = Validade()
    if tipo in TIPOS_VALIDADE_OBRIGATORIA:
        v.motivos.append("validade não identificada no documento")
    return v


def status(data_validade: date | None, tipo: str | None, hoje: date | None = None) -> tuple[str, int | None]:
    """(status, dias_restantes) — calculado sempre com a data de hoje."""
    if data_validade is None:
        return ("indeterminado" if tipo in TIPOS_COM_VALIDADE else "sem_validade"), None
    dias = (data_validade - (hoje or util.hoje())).days
    if dias < 0:
        return "vencido", dias
    if dias <= settings.VALIDADE_ALERTA_DIAS:
        return "vencendo", dias
    return "vigente", dias
