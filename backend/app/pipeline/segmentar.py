"""Etapa 4 — Segmentação: decide onde cada documento começa e termina.

Função PURA (não toca banco nem storage) → fácil de testar e de calibrar
com os dados de teste da organização.

Para cada página, combina sinais em ordem de força:
  1. "Página 2 de 3"            → continuação certa
  2. "Página 1 de 3"            → início certo
  3. título no topo (+ modelo)     → início provável
  4. modelo diz que é início       → início possível
  5. CPF de outra pessoa          → início provável (chave identificadora)
  6. tipo mudou (ambos confiáveis) → início fraco
  7. página em branco           → separador (fecha o documento)
Cada decisão gera uma confiança de corte; a confiança do documento é a menor
entre (tipo, cortes, qualidade do OCR).
"""
from collections import defaultdict
from dataclasses import dataclass, field

from app.config import settings
from app.tipos import DESCONHECIDO


@dataclass
class PaginaInfo:
    numero: int
    tipo: str
    conf_tipo: float
    em_branco: bool = False
    falhou: bool = False
    divergente: bool = False
    ocr_conf: float = 100.0
    inicio_llm: bool | None = None
    sinais: dict = field(default_factory=dict)


@dataclass
class DocProposto:
    paginas: list[int] = field(default_factory=list)
    tipo: str = DESCONHECIDO
    confianca: float = 0.0
    motivos: list[str] = field(default_factory=list)
    revisao: bool = False
    _cortes: list[float] = field(default_factory=list)
    _infos: list[PaginaInfo] = field(default_factory=list)


def _decidir(p: PaginaInfo, atual: DocProposto | None, forcar_novo: bool) -> tuple[bool, float, str | None]:
    """Retorna (novo_documento?, confiança_do_corte, motivo_de_alerta)."""
    s = p.sinais or {}
    x = s.get("pagina_x")
    titulo = s.get("titulo_topo")

    if atual is None or forcar_novo:
        forte = x == 1 or titulo is not None
        return True, 0.95 if forte else 0.85, None
    if x is not None and x > 1:
        if titulo or p.inicio_llm:
            return False, 0.6, f"pág. {p.numero + 1}: diz 'página {x}', mas parece início"
        return False, 0.97, None
    if x == 1:
        return True, 0.97, None
    if titulo and p.inicio_llm is not False:
        return True, 0.9, None
    if titulo and p.inicio_llm is False:
        return True, 0.6, f"pág. {p.numero + 1}: título no topo, mas modelo diz continuação"
    # chave identificadora: a página traz o CPF de OUTRA pessoa (impressões sem nenhuma em comum)
    cpfs_pag = {c["h"] for c in s.get("cpfs", [])}
    cpfs_doc = {c["h"] for i in atual._infos for c in (i.sinais or {}).get("cpfs", [])}
    if cpfs_pag and cpfs_doc and not (cpfs_pag & cpfs_doc):
        return True, 0.8, None
    if p.inicio_llm:
        return True, 0.75, None
    tipo_atual = _tipo_votado(atual._infos)[0]
    if (p.tipo != DESCONHECIDO and tipo_atual != DESCONHECIDO and p.tipo != tipo_atual
            and p.conf_tipo >= 0.6):
        return True, 0.65, f"pág. {p.numero + 1}: corte inferido só pela mudança de tipo"
    # continuação
    if p.tipo == tipo_atual:
        return False, 0.9, None
    if p.tipo == DESCONHECIDO:
        return False, 0.8, None
    return False, 0.6, f"pág. {p.numero + 1}: tipo diferente com baixa confiança"


def _tipo_votado(infos: list[PaginaInfo]) -> tuple[str, float]:
    votos, confs = defaultdict(float), defaultdict(list)
    for i in infos:
        if i.tipo != DESCONHECIDO:
            votos[i.tipo] += i.conf_tipo
            confs[i.tipo].append(i.conf_tipo)
    if not votos:
        return DESCONHECIDO, 0.0
    vencedor = max(votos, key=votos.get)
    participacao = votos[vencedor] / sum(votos.values())
    media = sum(confs[vencedor]) / len(confs[vencedor])
    return vencedor, media * participacao


def _fechar(doc: DocProposto, limiar: float) -> DocProposto:
    doc.tipo, conf_tipo = _tipo_votado(doc._infos)
    conf = min([conf_tipo] + doc._cortes)

    ocr_medio = sum(i.ocr_conf for i in doc._infos) / len(doc._infos)
    if ocr_medio < 60:
        conf *= 0.85
        doc.motivos.append(f"OCR de baixa qualidade ({ocr_medio:.0f}%)")

    primeiro = doc._infos[0].sinais or {}
    n_esperado = primeiro.get("pagina_n")
    if primeiro.get("pagina_x") == 1 and n_esperado and n_esperado != len(doc.paginas):
        conf = min(conf, 0.5)
        doc.motivos.append(f"esperava {n_esperado} páginas, encontrou {len(doc.paginas)}")
    if any(i.divergente for i in doc._infos):
        doc.motivos.append("regras e modelo discordam do tipo")
    if any(i.falhou for i in doc._infos):
        conf = 0.0
        doc.motivos.append("falha no processamento de página")
    if doc.tipo == DESCONHECIDO:
        doc.motivos.append("tipo não identificado")

    doc.confianca = round(conf, 3)
    if doc.confianca < limiar and not doc.motivos:
        doc.motivos.append(f"confiança {doc.confianca:.2f} abaixo do limiar de revisão ({limiar:.2f})")
    doc.revisao = doc.confianca < limiar or doc.tipo == DESCONHECIDO or bool(doc.motivos)
    return doc


def segmentar(paginas: list[PaginaInfo], limiar: float | None = None) -> list[DocProposto]:
    limiar = settings.LIMIAR_REVISAO if limiar is None else limiar
    docs: list[DocProposto] = []
    atual: DocProposto | None = None
    forcar_novo = False

    for p in sorted(paginas, key=lambda i: i.numero):
        if p.em_branco and settings.BRANCO_COMO_SEPARADOR:
            if atual:
                docs.append(_fechar(atual, limiar))
                atual = None
            forcar_novo = True
            continue  # página separadora não entra em nenhum documento

        novo, conf_corte, alerta = _decidir(p, atual, forcar_novo)
        forcar_novo = False
        if novo:
            if atual:
                docs.append(_fechar(atual, limiar))
            atual = DocProposto()
        atual.paginas.append(p.numero)
        atual._infos.append(p)
        atual._cortes.append(conf_corte)
        if alerta:
            atual.motivos.append(alerta)

    if atual:
        docs.append(_fechar(atual, limiar))
    return docs
