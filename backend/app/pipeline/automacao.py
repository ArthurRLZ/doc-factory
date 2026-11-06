"""Meta de automação: quanto vai para revisão humana em cada limiar de confiança.

- O limiar de revisão pode ser mudado em tempo de execução (fica na tabela `configuracoes`).
- A CURVA mostra, para cada limiar, quantos documentos seriam aprovados automaticamente.
- A ACURÁCIA é MEDIDA a partir das revisões humanas (o gabarito): documento aprovado sem mudança
  = o sistema acertou; tipo trocado, dividido ou juntado = errou. Sem revisões suficientes,
  a acurácia fica "sem dados" — nada é inventado.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Configuracao, Documento, Revisao
from app.status import StatusRevisao

CHAVE_LIMIAR = "limiar_revisao"

PREFIXO_MOTIVO_LIMIAR = "confiança "         # motivo gerado só pelo limiar (os outros são bloqueantes)
ACOES_ERRO = {"alterar_tipo", "dividir", "juntar_proximo"}
LIMIARES = [round(0.50 + 0.05 * i, 2) for i in range(10)] + [0.97, 0.99]
AMOSTRA_MINIMA = 5


def obter_limiar(db: Session) -> float:
    c = db.get(Configuracao, CHAVE_LIMIAR)
    try:
        return float(c.valor) if c else settings.LIMIAR_REVISAO
    except ValueError:
        return settings.LIMIAR_REVISAO


def motivos_bloqueantes(d: Documento) -> list[str]:
    """Motivos que mandam para revisão independentemente do limiar (tipo desconhecido, validade, divergência...)."""
    return [m for m in (d.motivos or []) if not m.startswith(PREFIXO_MOTIVO_LIMIAR)]


def risco_bloqueia(d: Documento) -> bool:
    """Sinal de fraude manda para revisão independentemente do limiar (mexer no limiar não reaprova)."""
    return d.risco == "alto_risco" or (d.risco == "atencao" and settings.FRAUDE_ATENCAO_REVISAO)


def precisa_revisao(d: Documento, limiar: float) -> bool:
    return d.confianca < limiar or bool(motivos_bloqueantes(d)) or risco_bloqueia(d)


def definir_limiar(db: Session, limiar: float, usuario: str, aplicar: bool = True) -> int:
    """Grava o novo limiar e (opcional) reavalia os documentos que ainda não foram revisados por uma pessoa.
    Retorna quantos documentos mudaram de situação."""
    c = db.get(Configuracao, CHAVE_LIMIAR) or Configuracao(chave=CHAVE_LIMIAR, valor="")
    c.valor, c.alterado_por = str(limiar), usuario
    db.add(c)
    mudaram = 0
    if aplicar:
        for d in db.scalars(select(Documento).where(Documento.status_revisao.in_((StatusRevisao.AUTO_APROVADO, StatusRevisao.PENDENTE)))):
            outros = motivos_bloqueantes(d)
            novo = StatusRevisao.PENDENTE if precisa_revisao(d, limiar) else StatusRevisao.AUTO_APROVADO
            motivos = outros or ([f"{PREFIXO_MOTIVO_LIMIAR}{d.confianca:.2f} abaixo do limiar de revisão ({limiar:.2f})"]
                                 if d.confianca < limiar else [])
            if novo != d.status_revisao:
                mudaram += 1
            d.status_revisao, d.motivos = novo, motivos
    db.commit()
    return mudaram


def _gabarito(db: Session) -> list[tuple[float, bool]]:
    """(confiança que o sistema deu, acertou?) para cada documento que uma pessoa revisou."""
    acoes: dict[str, set[str]] = {}
    for r in db.scalars(select(Revisao).where(Revisao.documento_id.is_not(None))):
        acoes.setdefault(r.documento_id, set()).add(r.acao)
    out = []
    for d in db.scalars(select(Documento).where(Documento.id.in_(list(acoes)))):
        a = acoes[d.id]
        if a & ACOES_ERRO:
            out.append((d.confianca, False))
        elif "aprovar" in a:
            out.append((d.confianca, True))
    return out


def curva(db: Session) -> dict:
    docs = list(db.scalars(select(Documento)))
    gab = _gabarito(db)
    atual = obter_limiar(db)
    pontos = []
    for lim in sorted(set(LIMIARES + [round(atual, 2)])):
        auto = sum(1 for d in docs if not precisa_revisao(d, lim))
        amostra = [ok for conf, ok in gab if conf >= lim]       # o que seria aprovado sozinho neste limiar
        pontos.append({
            "limiar": lim, "atual": abs(lim - atual) < 1e-9,
            "automaticos": auto, "para_revisao": len(docs) - auto,
            "percentual_automatico": round(100 * auto / len(docs), 1) if docs else 0.0,
            "acuracia_estimada": round(100 * sum(amostra) / len(amostra), 1) if len(amostra) >= AMOSTRA_MINIMA else None,
            "amostra": len(amostra),
        })
    acertos = sum(ok for _, ok in gab)
    return {
        "limiar_atual": atual, "limiar_padrao": settings.LIMIAR_REVISAO, "documentos": len(docs),
        "curva": pontos,
        "acuracia_medida": {"documentos_revisados": len(gab), "corretos": acertos,
                            "percentual": round(100 * acertos / len(gab), 1) if gab else None,
                            "observacao": None if len(gab) >= AMOSTRA_MINIMA else
                            f"poucas revisões ({len(gab)}): a acurácia aparece a partir de {AMOSTRA_MINIMA}"},
    }


def sugerir(db: Session, meta_acuracia: float) -> dict:
    """Menor limiar (= mais automação) cuja acurácia medida atinge a meta."""
    c = curva(db)
    for p in c["curva"]:
        if p["acuracia_estimada"] is not None and p["acuracia_estimada"] >= meta_acuracia:
            return {"meta": meta_acuracia, "limiar_sugerido": p["limiar"], "ponto": p}
    return {"meta": meta_acuracia, "limiar_sugerido": None, "ponto": None,
            "observacao": "ainda não há revisões suficientes para garantir essa meta; mantenha o limiar atual"}


def uso_da_pre_revisao(db: Session) -> dict:
    """Quantas revisões tinham sugestão da pré-revisão (F2) e em quantas o revisor fez o que foi sugerido."""
    from app.models import Revisao
    marcas = [r.get("seguiu_sugestao") for r in db.scalars(select(Revisao.depois)) if isinstance(r, dict)]
    com = [m for m in marcas if m is not None]
    seguidas = sum(1 for m in com if m)
    return {"revisoes_com_sugestao": len(com), "seguidas": seguidas,
            "percentual": round(100 * seguidas / len(com), 1) if com else None}
