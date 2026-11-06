"""Função/cargo do trabalhador → NRs exigidas no checklist (F3).

Por que a regra vem antes da IA: "Função: Eletricista" escrito no ASO é lido por padrão de texto, de graça e
auditável. A IA só entra quando o documento não tem esse rótulo, e só pode escolher uma chave da tabela fechada
FUNCOES_NR (tipos.py), com evidência copiada do texto — que é conferida.
"""
import logging
import re

from sqlalchemy.orm import Session

from app.llm import contador
from app.models import Documento, Trabalhador
from app.pipeline.classificar import normalizar
from app.pipeline.validade import evidencia_no_texto
from app.tipos import FUNCOES_NR

log = logging.getLogger(__name__)

# preferência: ASO (mais recente e confiável), depois CTPS/ficha de registro, depois ficha de EPI
TIPOS_COM_FUNCAO = ["ASO", "CTPS", "FICHA_EPI"]
_RX_ROTULO = re.compile(r"(?im)^[^\n]*?\b(fun[cç][aã]o|cargo|ocupa[cç][aã]o)\s*:\s*([^\n]{2,80})")


def extrair_funcao_por_regra(texto: str) -> tuple[str, str] | None:
    """('Eletricista de manutenção', 'Função: Eletricista de manutenção') ou None (sem rótulo no texto)."""
    m = _RX_ROTULO.search(texto or "")
    if not m:
        return None
    valor = re.split(r"\s{2,}|\bCBO\b", m.group(2).strip())[0].strip(" .;,-")
    if not valor or valor.startswith("["):        # campo anonimizado ou vazio
        return None
    return valor, m.group(0).strip()[:300]


def mapear_funcao(valor: str | None) -> str | None:
    """Chave de FUNCOES_NR cujo apelido aparece no texto da função (o apelido mais longo vence)."""
    n = normalizar(valor or "")
    candidatos = [(len(a), chave) for chave, f in FUNCOES_NR.items() for a in f["apelidos"]
                  if re.search(rf"\b{re.escape(a)}\b", n)]
    return max(candidatos)[1] if candidatos else None


def extrair_funcao_por_llm(llm, texto: str) -> tuple[str, str | None, str] | None:
    """(funcao, chave, evidencia) validado; None se a IA não ajudar ou inventar."""
    fn = getattr(llm, "extrair_funcao", None) if llm else None
    if not fn:
        return None
    try:
        r = fn(texto, {k: f["nome"] for k, f in FUNCOES_NR.items()})
    except Exception:
        log.exception("IA falhou ao extrair a função")
        return None
    if not isinstance(r, dict) or not r.get("funcao"):
        return None
    chave, evidencia = r.get("chave"), r.get("evidencia")
    if chave is not None and chave not in FUNCOES_NR:
        return None                                   # fora da lista fechada
    if not evidencia or not evidencia_no_texto(str(evidencia), texto):
        return None                                   # evidência inventada
    return str(r["funcao"])[:120], chave, str(evidencia)[:300]


def atualizar_funcao(db: Session, t: Trabalhador, documentos: list[Documento], llm=None,
                     lote_id: str | None = None) -> None:
    """Lê a função nos documentos do trabalhador (regra → IA). Não sobrescreve correção manual."""
    if t.funcao_origem == "manual":
        return
    docs = sorted((d for d in documentos if d.trabalhador_id == t.id and d.tipo in TIPOS_COM_FUNCAO),
                  key=lambda d: TIPOS_COM_FUNCAO.index(d.tipo))
    for d in docs:
        achou = extrair_funcao_por_regra(d.texto or "")
        if achou:
            t.funcao, t.funcao_evidencia = achou[0][:120], achou[1]
            t.funcao_chave, t.funcao_origem = mapear_funcao(achou[0]), "texto"
            return
    if llm and getattr(llm, "extrair_funcao", None):
        for d in docs:
            if not (d.texto or "").strip():
                continue
            r = extrair_funcao_por_llm(llm, d.texto)
            if lote_id:
                contador.registrar(db, lote_id, "outras")
            if r:
                t.funcao, t.funcao_chave, t.funcao_evidencia = r
                t.funcao_origem = "ia"
                return
