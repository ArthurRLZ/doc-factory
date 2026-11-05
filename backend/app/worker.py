"""Worker do pipeline — rode quantos quiser em paralelo.

    python -m app.worker                 # loop infinito
    python -m app.worker --uma-vez       # processa tudo que está pendente e sai (testes)
    python -m app.worker --recuperar-agora   # assume que nenhum outro worker está vivo (demo de retomada)

RETOMADA APÓS FALHA:
  - cada página tem status no banco; o worker só pega 'pendente' ou 'erro' (com tentativas < MAX)
  - se o worker morre no meio, a página fica 'processando'; após WORKER_STALE_MIN ela volta a 'pendente'
  - processar_pagina é idempotente → reprocessar uma página não duplica nada
  - no PostgreSQL usamos SELECT ... FOR UPDATE SKIP LOCKED → N workers sem pegar a mesma página
"""
import argparse
import logging
import os
import signal
import threading
import time
import traceback
from datetime import timedelta

from sqlalchemy import and_, or_, select, update

from app.config import settings
from app.db import E_POSTGRES, SessionLocal, init_db
from app.models import Lote, Pagina, agora
from app.pipeline.orquestrador import finalizar_lote_se_pronto, processar_pagina

# 1 thread por Tesseract: com vários workers em paralelo isso é MAIS rápido (evita disputa de CPU)
os.environ.setdefault("OMP_THREAD_LIMIT", "1")

log = logging.getLogger("worker")
_parar = threading.Event()


def recuperar_travadas(db, tudo: bool = False) -> int:
    limite = agora() - timedelta(minutes=settings.WORKER_STALE_MIN)
    cond = Pagina.status == "processando"
    if not tudo:
        cond = and_(cond, Pagina.atualizado_em < limite)
    n = db.execute(update(Pagina).where(cond).values(status="pendente")).rowcount
    # lote que travou durante a segmentação volta para 'processando' e será finalizado de novo
    cond_l = Lote.status == "segmentando"
    if not tudo:
        cond_l = and_(cond_l, Lote.atualizado_em < limite)
    db.execute(update(Lote).where(cond_l).values(status="processando"))
    db.commit()
    if n:
        log.warning("recuperadas %d páginas travadas", n)
    return n


def reivindicar_pagina(db) -> Pagina | None:
    q = (select(Pagina)
         .where(or_(Pagina.status == "pendente",
                    and_(Pagina.status == "erro", Pagina.tentativas < settings.MAX_TENTATIVAS)))
         .order_by(Pagina.id).limit(1))
    if E_POSTGRES:
        q = q.with_for_update(skip_locked=True)
    p = db.scalars(q).first()
    if not p:
        db.rollback()
        return None
    p.status, p.tentativas, p.atualizado_em = "processando", p.tentativas + 1, agora()
    db.commit()
    return p


def ciclo(db) -> bool:
    """Processa UMA página. Retorna False se não havia nada a fazer."""
    p = reivindicar_pagina(db)
    if not p:
        # lotes com todas as páginas prontas mas não finalizados (ex.: crash entre etapas)
        for lote_id in db.scalars(select(Lote.id).where(Lote.status == "processando")).all():
            finalizar_lote_se_pronto(db, lote_id)
        return False

    pid, lote_id, numero = p.id, p.lote_id, p.numero
    inicio = time.perf_counter()
    try:
        processar_pagina(db, pid)
        log.info("lote %s pág %d ok (%.1fs)", lote_id[:8], numero + 1, time.perf_counter() - inicio)
    except Exception as e:
        db.rollback()
        p = db.get(Pagina, pid)
        if _parar.is_set():   # interrompido por desligamento: devolve a página sem gastar tentativa
            p.status, p.tentativas = "pendente", p.tentativas - 1
            db.commit()
            return True
        p.status = "erro" if p.tentativas < settings.MAX_TENTATIVAS else "falhou"
        p.erro = "".join(traceback.format_exception_only(type(e), e))[:2000]
        db.commit()
        log.error("lote %s pág %d %s: %s", lote_id[:8], numero + 1, p.status, e)
    finalizar_lote_se_pronto(db, lote_id)
    return True


def rodar(uma_vez: bool = False, recuperar_agora: bool = False) -> None:
    init_db()
    with SessionLocal() as db:
        recuperar_travadas(db, tudo=recuperar_agora)
    ultimo_check = time.monotonic()
    while not _parar.is_set():
        with SessionLocal() as db:
            if time.monotonic() - ultimo_check > 30:
                recuperar_travadas(db)
                ultimo_check = time.monotonic()
            trabalhou = ciclo(db)
        if not trabalhou:
            if uma_vez:
                return
            _parar.wait(settings.WORKER_POLL_S)


def iniciar_em_thread() -> threading.Thread:
    t = threading.Thread(target=rodar, name="worker-inline", daemon=True)
    t.start()
    return t


def parar() -> None:
    _parar.set()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--uma-vez", action="store_true")
    ap.add_argument("--recuperar-agora", action="store_true")
    a = ap.parse_args()
    # SIGTERM (docker stop) → termina a página atual e sai limpo
    signal.signal(signal.SIGTERM, lambda *_: _parar.set())
    signal.signal(signal.SIGINT, lambda *_: _parar.set())
    rodar(uma_vez=a.uma_vez, recuperar_agora=a.recuperar_agora)
