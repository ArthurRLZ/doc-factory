"""Checklist de documentos exigidos por trabalhador: o que falta, o que está vencido e o que está duplicado.

Exigidos: DOCUMENTOS_EXIGIDOS_TRABALHADOR em tipos.py (ex.: identidade, CTPS, ASO, ficha de EPI).
Para cada tipo exigido vale o documento MAIS RECENTE (pela validade, ou pela data de envio);
os mais antigos do mesmo tipo aparecem como "substituídos" — não contam como pendência.
"""
from datetime import datetime

from app.config import settings
from app.models import Documento, Trabalhador
from app.pipeline import validade
from app.tipos import DOCUMENTOS_EXIGIDOS_TRABALHADOR, FUNCOES_NR, PREFIXO_TOKEN_NR, nome_tipo

# do melhor para o pior (para resumir a situação)
GRAVIDADE = {"ok": 0, "sem_validade": 0, "vigente": 0, "vencendo": 1, "indeterminado": 1, "vencido": 2, "faltando": 2}
SITUACAO = {0: "regular", 1: "atencao", 2: "irregular"}


def _mais_recente(docs: list[Documento]) -> Documento:
    return max(docs, key=lambda d: (d.validade_data or datetime.min.date(), d.criado_em or datetime.min))


def nr_do_certificado(d: Documento) -> str | None:
    """'NR-10' a partir do campo 'norma' do resumo ou, na falta, do texto do certificado."""
    for fonte in ((d.campos or {}).get("norma"), d.texto):
        m = validade.RX_NR.search(str(fonte or ""))
        if m:
            return f"NR-{int(m.group(1) or m.group(2))}"
    return None


def exigidos_do_trabalhador(t: Trabalhador) -> list[str]:
    """Base fixa + certificados de NR que a função do trabalhador exige ('CERTIFICADO_NR:NR-10')."""
    base = list(DOCUMENTOS_EXIGIDOS_TRABALHADOR)
    if settings.FUNCAO_EXIGENCIAS_ATIVO and t.funcao_chave in FUNCOES_NR:
        base += [f"{PREFIXO_TOKEN_NR}{nr}" for nr in FUNCOES_NR[t.funcao_chave]["nrs"]]
    return base


def nome_exigido(token: str) -> str:
    if token.startswith(PREFIXO_TOKEN_NR):
        return f"Certificado {token[len(PREFIXO_TOKEN_NR):]}"
    return nome_tipo(token)


def docs_do_exigido(token: str, documentos: list[Documento]) -> list[Documento]:
    """Documentos que atendem a um item exigido (tipo simples ou 'CERTIFICADO_NR:NR-xx')."""
    if token.startswith(PREFIXO_TOKEN_NR):
        nr = token[len(PREFIXO_TOKEN_NR):]
        return [d for d in documentos if d.tipo == "CERTIFICADO_NR" and nr_do_certificado(d) == nr]
    return [d for d in documentos if d.tipo == token]


def avaliar(t: Trabalhador, exigidos: list[str] | None = None) -> dict:
    da_funcao = exigidos is None
    exigidos = exigidos_do_trabalhador(t) if exigidos is None else (exigidos or DOCUMENTOS_EXIGIDOS_TRABALHADOR)
    motivo_funcao = (f"exigido para a função {FUNCOES_NR[t.funcao_chave]['nome']}"
                     if da_funcao and t.funcao_chave in FUNCOES_NR else None)
    cobertos: set[str] = set()                      # documentos que já atendem um item exigido

    itens, duplicados = [], []
    for tipo in exigidos:
        docs = docs_do_exigido(tipo, t.documentos)
        extra = {"motivo_exigencia": motivo_funcao} if tipo.startswith(PREFIXO_TOKEN_NR) and motivo_funcao else {}
        if not docs:
            itens.append({"tipo": tipo, "tipo_nome": nome_exigido(tipo), "status": "faltando", "documento_id": None,
                          "validade": None, "observacao": "documento exigido não encontrado"} | extra)
            continue
        cobertos.update(d.id for d in docs)
        atual = _mais_recente(docs)
        st, dias = validade.status(atual.validade_data, atual.tipo)
        obs = {"vencido": f"vencido há {abs(dias or 0)} dia(s)", "vencendo": f"vence em {dias} dia(s)",
               "indeterminado": "validade não identificada"}.get(st)
        itens.append({"tipo": tipo, "tipo_nome": nome_exigido(tipo), "status": "ok" if st in ("vigente", "sem_validade") else st,
                      "documento_id": atual.id, "validade": atual.validade_data.isoformat() if atual.validade_data else None,
                      "observacao": obs} | extra)
        if len(docs) > 1:
            duplicados.append({"tipo": tipo, "tipo_nome": nome_exigido(tipo), "vigente_id": atual.id,
                               "substituidos": [d.id for d in docs if d.id != atual.id]})
    # documentos não exigidos que estão vencidos também pesam (ex.: certificado de NR)
    extras_vencidos = []
    for d in t.documentos:
        if d.tipo in exigidos or d.id in cobertos:
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
