"""Etapa 3 — Classificação por página (regras + modelo) e sinais de início de documento."""
import re
import unicodedata
from dataclasses import dataclass, field

from app.tipos import DESCONHECIDO, TIPOS

_TITULOS = {cod: [re.compile(rx) for rx in t["titulos"]] for cod, t in TIPOS.items()}
_RX_PAGINA = re.compile(r"\bp(?:ag|agina)?\.?\s*(\d{1,3})\s*(?:de|/)\s*(\d{1,3})\b")
_RX_FOLHA = re.compile(r"\bfl(?:s|ha)?\.?\s*(\d{1,3})\s*/\s*(\d{1,3})\b")


def normalizar(texto: str) -> str:
    """minúsculo + sem acento: 'CERTIDÃO' → 'certidao'."""
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t.lower())


@dataclass
class Classificacao:
    tipo: str
    confianca: float
    scores: dict = field(default_factory=dict)
    aprendizado_id: int | None = None      # correção humana que decidiu (se houve)


PESO_APRENDIZADO = 6   # uma correção humana vale mais que um título padrão (+3)


def classificar_por_regras(texto: str, texto_topo: str,
                           aprendidos: list[tuple[int, str, str]] | None = None) -> Classificacao:
    """aprendidos: [(id, título normalizado, tipo correto)] vindos das correções dos revisores."""
    t, topo = normalizar(texto), normalizar(texto_topo)
    scores = {}
    for cod, cfg in TIPOS.items():
        s = sum(1 for p in cfg["palavras"] if p in t)
        s += sum(3 for rx in _TITULOS[cod] if rx.search(topo))
        scores[cod] = s
    aprendido = None
    for ap_id, titulo, tipo in aprendidos or []:
        if titulo and tipo in scores and titulo in topo:
            scores[tipo] += PESO_APRENDIZADO
            aprendido = aprendido or ap_id
    melhor = max(scores, key=scores.get)
    topo_s, total = scores[melhor], sum(scores.values())
    if topo_s == 0:
        return Classificacao(DESCONHECIDO, 0.0, scores)
    # confiança = quão dominante é o vencedor × quanta evidência absoluta existe
    dominancia = topo_s / total
    evidencia = min(1.0, topo_s / 6)
    return Classificacao(melhor, round(dominancia * (0.5 + 0.5 * evidencia), 3), scores,
                         aprendido if aprendido is not None else None)


def texto_do_topo(palavras: list[dict], altura_pt: float, fracao: float = 0.3) -> str:
    limite = altura_pt * fracao
    return " ".join(w["t"] for w in palavras if w["y0"] <= limite)


def sinais_de_inicio(texto: str, texto_topo: str) -> dict:
    """Pistas determinísticas de que a página COMEÇA (ou CONTINUA) um documento."""
    t, topo = normalizar(texto), normalizar(texto_topo)
    sinais: dict = {"pagina_x": None, "pagina_n": None, "titulo_topo": None}
    m = _RX_PAGINA.search(t) or _RX_FOLHA.search(t)
    if m:
        x, n = int(m.group(1)), int(m.group(2))
        if 0 < x <= n <= 500:
            sinais["pagina_x"], sinais["pagina_n"] = x, n
    for cod, rxs in _TITULOS.items():
        if any(rx.search(topo) for rx in rxs):
            sinais["titulo_topo"] = cod
            break
    return sinais


def combinar(regra: Classificacao, tipo_llm: str | None, conf_llm: float | None) -> tuple[str, float, bool]:
    """Junta as duas opiniões. Retorna (tipo, confiança, divergente)."""
    if tipo_llm is None:
        return regra.tipo, regra.confianca, False
    conf_llm = conf_llm or 0.0
    if regra.tipo == DESCONHECIDO:
        return tipo_llm, conf_llm * 0.9, False      # só o modelo opinou
    if tipo_llm == regra.tipo:
        return regra.tipo, round(min(0.99, 1 - (1 - regra.confianca) * (1 - conf_llm)), 3), False
    # discordância: fica com a mais confiante, mas penaliza e marca p/ revisão
    if conf_llm > regra.confianca:
        return tipo_llm, round(conf_llm * 0.6, 3), True
    return regra.tipo, round(regra.confianca * 0.6, 3), True
