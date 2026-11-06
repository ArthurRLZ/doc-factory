"""Pré-revisão: antes de o revisor abrir um documento da fila, o sistema explica a dúvida e sugere o que fazer (F2).

Por que só sugerir: a decisão é do revisor. A IA explica em português e aponta trechos do texto; tudo é validado
(ação de uma lista fechada, tipo existente, evidência literal). Sem IA, ou se ela falhar, a explicação sai dos
motivos que o próprio pipeline já registrou ("origem": "regras").
"""
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.llm import contador
from app.models import Documento, Lote, Pagina
from app.pipeline.validade import evidencia_no_texto
from app.tipos import TIPOS, nome_tipo

log = logging.getLogger(__name__)

ACOES = {"aprovar", "alterar_tipo", "verificar_manual"}
MARGEM_SEGUNDO_TIPO = 0.15           # 2º tipo a menos de 15% do 1º nas regras = dúvida real de tipo


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def validar(resp, texto: str, tipo_atual: str) -> dict:
    """Resposta da IA → dicionário seguro. Rebaixa para 'verificar_manual' tudo que não se sustenta."""
    acao = getattr(resp, "acao_sugerida", None)
    acao = acao if acao in ACOES else "verificar_manual"
    tipo = getattr(resp, "tipo_sugerido", None)
    if tipo not in TIPOS or tipo == tipo_atual:
        tipo = None
    evid = [str(e)[:300] for e in (getattr(resp, "evidencias", None) or []) if evidencia_no_texto(str(e), texto)]
    if acao == "alterar_tipo" and (not tipo or not evid):
        acao, tipo = "verificar_manual", None
    if acao != "alterar_tipo":
        tipo = None
    try:
        conf = min(max(float(getattr(resp, "confianca", 0) or 0), 0.0), 1.0)
    except (TypeError, ValueError):
        conf = 0.0
    return {"explicacao": str(getattr(resp, "explicacao", "") or "").strip()[:400] or "Sem explicação.",
            "acao_sugerida": acao, "tipo_sugerido": tipo, "confianca": round(conf, 2), "evidencias": evid[:5],
            "origem": "ia", "gerado_em": _agora()}


def pre_revisao_por_regras(doc: Documento, paginas: list[Pagina]) -> dict:
    """Fallback determinístico: explica pelos motivos e só sugere outro tipo se as regras ficaram quase empatadas."""
    explicacao = "; ".join(doc.motivos or []) or "Documento marcado para conferência."
    acao, tipo = "verificar_manual", None
    for p in paginas:
        scores = {k: v for k, v in ((p.sinais or {}).get("scores") or {}).items() if k in TIPOS and v}
        if len(scores) < 2:
            continue
        (t1, s1), (t2, s2) = sorted(scores.items(), key=lambda kv: -kv[1])[:2]
        if s1 > 0 and (s1 - s2) / s1 < MARGEM_SEGUNDO_TIPO:
            candidato = t2 if t1 == doc.tipo else t1
            if candidato != doc.tipo:
                acao, tipo = "alterar_tipo", candidato
                explicacao += f"; as regras ficaram divididas entre {nome_tipo(t1)} e {nome_tipo(t2)}"
                break
    return {"explicacao": explicacao[:400], "acao_sugerida": acao, "tipo_sugerido": tipo, "confianca": 0.0,
            "evidencias": [], "origem": "regras", "gerado_em": _agora()}


def gerar(db: Session, lote: Lote, doc: Documento, paginas: list[Pagina], llm, usar_ia: bool = True) -> dict:
    """IA (validada) → senão regras. Conta a chamada no lote quando a IA é consultada."""
    fn = getattr(llm, "pre_revisar", None) if (llm and usar_ia) else None
    texto = doc.texto or ""
    if fn and texto.strip():
        candidatos = sorted({p.tipo_regra for p in paginas if p.tipo_regra and p.tipo_regra in TIPOS})
        try:
            resp = fn(nome_tipo(doc.tipo), list(doc.motivos or []), [a.get("mensagem", "") for a in doc.alertas or []],
                      texto, candidatos)
        except Exception:
            log.exception("IA falhou na pré-revisão")
            resp = None
        contador.registrar(db, lote.id, "outras")
        if resp is not None:
            return validar(resp, texto, doc.tipo)
    return pre_revisao_por_regras(doc, paginas)


def seguiu(pre: dict | None, acao: str, tipo_escolhido: str | None) -> bool | None:
    """O revisor fez o que a pré-revisão sugeriu? None se não havia sugestão acionável."""
    if not pre or pre.get("acao_sugerida") == "verificar_manual":
        return None
    if pre["acao_sugerida"] == "alterar_tipo":
        return acao == "alterar_tipo" and tipo_escolhido == pre.get("tipo_sugerido")
    return acao == pre["acao_sugerida"]
