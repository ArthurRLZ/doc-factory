"""Contador de chamadas de IA por lote ("só 3 de 14 páginas precisaram de IA").

Por que UPDATE em SQL: vários workers processam páginas do mesmo lote ao mesmo tempo; ler-e-somar em Python
perderia incrementos. Não faz commit: entra na transação de quem chamou.
"""
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import Lote, Pagina

_COLUNAS = {"classificacao": Lote.llm_chamadas_classificacao, "resumo": Lote.llm_chamadas_resumo,
            "outras": Lote.llm_chamadas_outras}


def registrar(db: Session, lote_id: str, categoria: str, pagina_id: int | None = None) -> None:
    """Conta UMA chamada ao modelo (respondeu ou não: a chamada custou do mesmo jeito)."""
    col = _COLUNAS[categoria]
    db.execute(update(Lote).where(Lote.id == lote_id).values({col: col + 1}))
    if categoria == "classificacao" and pagina_id is not None:
        res = db.execute(update(Pagina).where(Pagina.id == pagina_id, Pagina.llm_chamado.is_(False))
                         .values(llm_chamado=True))
        if res.rowcount == 1:
            db.execute(update(Lote).where(Lote.id == lote_id).values(llm_paginas=Lote.llm_paginas + 1))


def zerar(db: Session, lote_id: str, numeros_paginas: list[int] | None = None) -> None:
    """Reprocessar: o contador reflete só a última execução."""
    db.execute(update(Lote).where(Lote.id == lote_id).values(
        llm_chamadas_classificacao=0, llm_chamadas_resumo=0, llm_chamadas_outras=0, llm_paginas=0))
    q = update(Pagina).where(Pagina.lote_id == lote_id)
    if numeros_paginas is not None:
        q = q.where(Pagina.numero.in_(numeros_paginas))
    db.execute(q.values(llm_chamado=False))
    # páginas que NÃO foram reprocessadas mantêm a marca; o total de páginas com IA segue coerente
    restantes = db.scalar(select(func.count()).select_from(Pagina)
                          .where(Pagina.lote_id == lote_id, Pagina.llm_chamado.is_(True))) or 0
    db.execute(update(Lote).where(Lote.id == lote_id).values(llm_paginas=restantes))
