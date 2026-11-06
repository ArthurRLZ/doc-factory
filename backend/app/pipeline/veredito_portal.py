"""Veredito que o FORNECEDOR vê no portal: aprovado, reprovado (com motivo claro) ou em análise (F7).

Por que uma lista branca de mensagens: o fornecedor nunca pode ver alerta de fraude, texto/OCR, CPF ou motivos
internos de revisão. Só as frases abaixo saem daqui; "em análise" é neutro de propósito.
"""
from datetime import datetime

from app.models import Documento, Pagina
from app.pipeline import validade
from app.pipeline.checklist import docs_do_exigido, nome_exigido
from app.status import StatusRevisao
from app.tipos import DESCONHECIDO, TIPOS

MSG_DESCONHECIDO = "Não conseguimos identificar este documento. Envie uma imagem mais nítida."
MSG_ILEGIVEL = "Documento ilegível. Reenvie com melhor qualidade."
MSG_VENCIDO = "Documento vencido em {data}. Envie a versão atualizada."
MSG_EM_ANALISE = "Recebido. Nossa equipe vai conferir este documento."
MSG_VENCENDO = "Válido, mas vence em {dias} dia(s). Providencie a renovação."
MSG_ERRO_ARQUIVO = "Não foi possível ler este arquivo. Tente reenviar."
OCR_MINIMO = 50.0


def avaliar_documento(doc: Documento, paginas: list[Pagina] | None = None) -> dict:
    """{"veredito": "aprovado|reprovado|em_analise", "motivo", "aviso"} — para no primeiro caso que se aplica."""
    humano = doc.status_revisao == StatusRevisao.REVISADO       # a decisão do revisor manda
    if doc.tipo == DESCONHECIDO and not humano:
        return {"veredito": "reprovado", "motivo": MSG_DESCONHECIDO, "aviso": None}
    escaneadas = [p.ocr_confianca for p in (paginas or []) if not p.nativa and p.ocr_confianca is not None]
    if escaneadas and not humano and sum(escaneadas) / len(escaneadas) < OCR_MINIMO:
        return {"veredito": "reprovado", "motivo": MSG_ILEGIVEL, "aviso": None}
    st, dias = validade.status(doc.validade_data, doc.tipo)
    if st == "vencido":
        return {"veredito": "reprovado", "motivo": MSG_VENCIDO.format(data=f"{doc.validade_data:%d/%m/%Y}"), "aviso": None}
    if not humano and (doc.risco in ("alto_risco", "atencao") or doc.status_revisao == StatusRevisao.PENDENTE):
        return {"veredito": "em_analise", "motivo": MSG_EM_ANALISE, "aviso": None}
    if st == "vencendo":
        return {"veredito": "aprovado", "motivo": None, "aviso": MSG_VENCENDO.format(dias=dias)}
    return {"veredito": "aprovado", "motivo": None, "aviso": None}


def mais_recente(docs: list[Documento]) -> Documento:
    """O último ENVIADO vale (reenvio substitui o anterior)."""
    return max(docs, key=lambda d: (d.criado_em or datetime.min, d.validade_data or datetime.min.date()))


def mais_recentes_por_exigido(exigidos: list[str], documentos: list[Documento]) -> dict[str, Documento]:
    saida = {}
    for item in exigidos:
        docs = docs_do_exigido(item, documentos)
        if docs:
            saida[item] = mais_recente(docs)
    return saida


def consolidar(exigidos: list[str], docs_mais_recentes: dict[str, Documento],
               vereditos: dict[str, dict] | None = None) -> list[dict]:
    """Situação de cada documento exigido: aprovado | reprovado | em_analise | nao_enviado."""
    vereditos = vereditos or {}
    saida = []
    for item in exigidos:
        d = docs_mais_recentes.get(item)
        if d is None:
            saida.append({"tipo": item, "tipo_nome": nome_exigido(item), "situacao": "nao_enviado",
                          "motivo": None, "aviso": None, "enviado_em": None})
            continue
        v = vereditos.get(d.id) or avaliar_documento(d)
        saida.append({"tipo": item, "tipo_nome": nome_exigido(item), "situacao": v["veredito"],
                      "motivo": v["motivo"], "aviso": v["aviso"], "enviado_em": d.criado_em})
    return saida


def exigido_valido(item: str) -> bool:
    if item.startswith("CERTIFICADO_NR:"):
        nr = item.split(":", 1)[1]
        return nr.startswith("NR-") and nr[3:].isdigit()
    return item in TIPOS
