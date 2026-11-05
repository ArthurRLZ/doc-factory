"""API — Document Factory.

    uvicorn app.main:app --reload        → http://localhost:8000/docs (Swagger)
"""
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from app.api import documentos, lotes
from app.api.deps import exigir_api_key
from app.config import settings
from app.db import SessionLocal, init_db
from app.models import Documento, Lote, Pagina

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    if settings.WORKER_INLINE:
        from app import worker
        worker.iniciar_em_thread()
    yield
    if settings.WORKER_INLINE:
        from app import worker
        worker.parar()


app = FastAPI(title="Document Factory", version="0.1.0", lifespan=lifespan,
              description="Separa, classifica e torna pesquisáveis lotes de documentos digitalizados.")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
                   allow_methods=["*"], allow_headers=["*"])

protegido = [Depends(exigir_api_key)]
app.include_router(lotes.router, dependencies=protegido)
app.include_router(documentos.router, dependencies=protegido)


@app.get("/health", tags=["infra"])
def health():
    return {"ok": True}


@app.get("/metricas", tags=["infra"], dependencies=protegido)
def metricas():
    """Números para o dashboard e para o pitch."""
    with SessionLocal() as db:
        por_status = dict(db.execute(select(Documento.status_revisao, func.count()).group_by(Documento.status_revisao)).all())
        total_docs = sum(por_status.values())
        return {
            "lotes": db.scalar(select(func.count()).select_from(Lote)),
            "paginas": db.scalar(select(func.count()).select_from(Pagina)),
            "paginas_por_status": dict(db.execute(select(Pagina.status, func.count()).group_by(Pagina.status)).all()),
            "documentos": total_docs,
            "documentos_por_tipo": dict(db.execute(select(Documento.tipo, func.count()).group_by(Documento.tipo)).all()),
            "documentos_por_revisao": por_status,
            "taxa_automacao": round(por_status.get("auto_aprovado", 0) / total_docs, 3) if total_docs else None,
            "confianca_media": db.scalar(select(func.avg(Documento.confianca))),
        }
