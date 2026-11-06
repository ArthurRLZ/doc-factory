"""Checklist de documentos exigidos por trabalhador: o que falta, o que está vencido e o que está duplicado.

Exigidos: DOCUMENTOS_EXIGIDOS_TRABALHADOR em tipos.py (ex.: identidade, CTPS, ASO, ficha de EPI).
Para cada tipo exigido vale o documento MAIS RECENTE (pela validade, ou pela data de envio);
os mais antigos do mesmo tipo aparecem como "substituídos" — não contam como pendência.
"""
from datetime import datetime

from app.models import Documento, Trabalhador
from app.pipeline import validade
from app.tipos import DOCUMENTOS_EXIGIDOS_TRABALHADOR, nome_tipo

# do melhor para o pior (para resumir a situação)
GRAVIDADE = {"ok": 0, "sem_validade": 0, "vigente": 0, "vencendo": 1, "indeterminado": 1, "vencido": 2, "faltando": 2}
SITUACAO = {0: "regular", 1: "atencao", 2: "irregular"}


def _mais_recente(docs: list[Documento]) -> Documento:
    return max(docs, key=lambda d: (d.validade_data or datetime.min.date(), d.criado_em or datetime.min))


def avaliar(t: Trabalhador, exigidos: list[str] | None = None) -> dict:
    exigidos = exigidos or DOCUMENTOS_EXIGIDOS_TRABALHADOR
    por_tipo: dict[str, list[Documento]] = {}
    for d in t.documentos:
        por_tipo.setdefault(d.tipo, []).append(d)

    itens, duplicados = [], []
    for tipo in exigidos:
        docs = por_tipo.get(tipo, [])
        if not docs:
            itens.append({"tipo": tipo, "tipo_nome": nome_tipo(tipo), "status": "faltando", "documento_id": None,
                          "validade": None, "observacao": "documento exigido não encontrado"})
            continue
        atual = _mais_recente(docs)
        st, dias = validade.status(atual.validade_data, atual.tipo)
        obs = {"vencido": f"vencido há {abs(dias or 0)} dia(s)", "vencendo": f"vence em {dias} dia(s)",
               "indeterminado": "validade não identificada"}.get(st)
        itens.append({"tipo": tipo, "tipo_nome": nome_tipo(tipo), "status": "ok" if st in ("vigente", "sem_validade") else st,
                      "documento_id": atual.id, "validade": atual.validade_data.isoformat() if atual.validade_data else None,
                      "observacao": obs})
        if len(docs) > 1:
            duplicados.append({"tipo": tipo, "tipo_nome": nome_tipo(tipo), "vigente_id": atual.id,
                               "substituidos": [d.id for d in docs if d.id != atual.id]})
    # documentos não exigidos que estão vencidos também pesam (ex.: certificado de NR)
    extras_vencidos = []
    for d in t.documentos:
        if d.tipo in exigidos:
            continue
        st, dias = validade.status(d.validade_data, d.tipo)
        if st in ("vencido", "vencendo"):
            extras_vencidos.append({"tipo": d.tipo, "tipo_nome": nome_tipo(d.tipo), "status": st,
                                    "documento_id": d.id, "validade": d.validade_data.isoformat(),
                                    "observacao": f"vencido há {abs(dias)} dia(s)" if st == "vencido" else f"vence em {dias} dia(s)"})

    pior = max([GRAVIDADE[i["status"]] for i in itens + extras_vencidos] or [0])
    faltando = [i["tipo"] for i in itens if i["status"] == "faltando"]
    vencidos = [i for i in itens + extras_vencidos if i["status"] == "vencido"]
    vencendo = [i for i in itens + extras_vencidos if i["status"] == "vencendo"]
    return {
        "situacao": SITUACAO[pior],
        "pendencias": len(faltando) + len(vencidos),
        "faltando": faltando, "vencidos": len(vencidos), "vencendo": len(vencendo),
        "checklist": itens, "outros_alertas": extras_vencidos, "duplicados": duplicados,
        "exigidos": exigidos,
    }
