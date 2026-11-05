"""Configuração comum dos testes: banco e storage temporários, sem modelo externo."""
import os
import subprocess
import sys
import tempfile

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix="docfactory_test_")
# precisa acontecer ANTES de qualquer import de app.* (as configurações são lidas no import)
os.environ.update(DATABASE_URL=f"sqlite:///{TMP}/t.db", DATA_DIR=TMP, LLM_PROVIDER="nenhum", DPI_OCR="200",
                  AUTH_ATIVO="false", API_KEY="", WORKER_INLINE="false", LIMIAR_REVISAO="0.80")


@pytest.fixture(scope="session")
def lote_pdf():
    caminho = os.path.join(TMP, "lote.pdf")
    subprocess.run([sys.executable, os.path.join(BASE, "scripts", "gerar_lote_teste.py"), caminho], check=True)
    return caminho


@pytest.fixture(scope="session")
def processado(lote_pdf):
    """Um lote de 11 páginas enviado e processado de ponta a ponta (compartilhado entre os testes)."""
    from fastapi.testclient import TestClient

    from app import worker
    from app.main import app

    with TestClient(app) as c:
        with open(lote_pdf, "rb") as f:
            r = c.post("/lotes", files={"arquivo": ("lote.pdf", f, "application/pdf")})
        assert r.status_code == 201, r.text
        lote = r.json()
        worker.rodar(uma_vez=True)
        yield c, lote
