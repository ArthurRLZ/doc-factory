"""Chave identificadora do trabalhador SEM guardar o CPF.

O CPF é lido do texto do OCR ANTES da anonimização e vira, na hora, uma impressão digital:
HMAC-SHA256(segredo, CPF). O banco guarda só a impressão (para agrupar os documentos da mesma
pessoa) e uma forma mascarada para exibição (***.982.247-**). Sem o segredo, a impressão não
permite voltar ao CPF.

Segredo: CPF_SEGREDO no .env (recomendado em produção). Sem ele, um segredo aleatório é gerado
uma vez e guardado na tabela de configurações (as impressões continuam estáveis entre reinícios).
"""
import hashlib
import hmac
import logging
import re
import secrets

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Configuracao

log = logging.getLogger(__name__)
CHAVE_SEGREDO = "segredo_impressao_cpf"
RX_CPF = re.compile(r"\b(\d{3})\.(\d{3})\.(\d{3})-(\d{2})\b|\b(\d{11})\b")


def cpf_valido(cpf: str) -> bool:
    d = [int(c) for c in cpf]
    if len(d) != 11 or len(set(d)) == 1:
        return False
    for n in (9, 10):
        soma = sum(d[i] * (n + 1 - i) for i in range(n))
        dv = (soma * 10) % 11 % 10
        if dv != d[n]:
            return False
    return True


def cpfs_no_texto(texto: str) -> list[str]:
    """CPFs válidos (só dígitos), na ordem em que aparecem, sem repetição."""
    achados = []
    for m in RX_CPF.finditer(texto or ""):
        cpf = "".join(g for g in m.groups() if g)
        if cpf_valido(cpf) and cpf not in achados:
            achados.append(cpf)
    return achados


def mascarado(cpf: str) -> str:
    return f"***.{cpf[3:6]}.{cpf[6:9]}-**"


def _segredo(db: Session) -> bytes:
    if settings.CPF_SEGREDO:
        return settings.CPF_SEGREDO.encode()
    c = db.get(Configuracao, CHAVE_SEGREDO)
    if not c:
        log.warning("CPF_SEGREDO não definido: gerando um segredo e guardando no banco (defina no .env em produção)")
        c = Configuracao(chave=CHAVE_SEGREDO, valor=secrets.token_hex(32), alterado_por="sistema")
        db.add(c)
        db.flush()
    return c.valor.encode()


def impressoes(db: Session, texto: str) -> list[dict]:
    """[{"h": impressão, "m": cpf mascarado}] para cada CPF válido do texto."""
    chave = _segredo(db)
    return [{"h": hmac.new(chave, cpf.encode(), hashlib.sha256).hexdigest()[:32], "m": mascarado(cpf)}
            for cpf in cpfs_no_texto(texto)]
