"""F0: contador de chamadas de IA por lote e "decidido por" (regra, IA, combinado, humano)."""
import json
import os
import subprocess
import sys

import httpx
import pytest

from app.models import Pagina
from app.pipeline.explicabilidade import decidido_por
from tests.conftest import BASE, TMP


def _pag(tipo, tipo_regra, tipo_llm=None, just=None):
    return Pagina(tipo=tipo, tipo_regra=tipo_regra, tipo_llm=tipo_llm,
                  sinais={"llm_justificativa": just} if just else {})


# ---------------------------------------------------------------- função pura
def test_decidido_por_regra():
    assert decidido_por([_pag("ASO", "ASO")], "ASO") == ("regra", None)


def test_decidido_por_ia():
    assert decidido_por([_pag("ASO", "CTPS", "ASO", "tem exame admissional")], "ASO") == ("ia", "tem exame admissional")


def test_decidido_por_combinado():
    assert decidido_por([_pag("ASO", "ASO", "ASO", "concorda")], "ASO") == ("combinado", "concorda")
    # a IA foi consultada mas a regra prevaleceu
    assert decidido_por([_pag("ASO", "ASO", "CTPS", "acho CTPS")], "ASO")[0] == "combinado"


def test_justificativa_truncada():
    assert len(decidido_por([_pag("ASO", "CTPS", "ASO", "x" * 900)], "ASO")[1]) == 500


# ---------------------------------------------------------------- sem LLM
def test_sem_llm_nao_conta_nada(lote_terceiros):
    c, lote = lote_terceiros
    ia = c.get(f"/lotes/{lote['id']}").json()["ia"]
    assert ia["chamadas_total"] == 0 and ia["percentual_paginas_com_ia"] == 0
    docs = c.get(f"/lotes/{lote['id']}/documentos").json()
    assert docs and all(d["decidido_por"] == "regra" and d["origem_texto"] == "Decidido por regras" for d in docs)
    painel = c.get("/painel").json()["ia"]
    assert set(painel) == {"chamadas_total", "paginas_com_ia", "paginas_total", "percentual_paginas_com_ia"}


# ---------------------------------------------------------------- com LLM simulado (MockTransport, sem rede)
def _cliente_falso():
    from app.llm.openai_compat import ClienteOpenAICompat

    def responder(req: httpx.Request) -> httpx.Response:
        sistema = json.loads(req.content)["messages"][0]["content"]
        if sistema.startswith("Você classifica"):
            conteudo = {"tipo": "ASO", "inicio_documento": True, "confianca": 0.9, "justificativa": "parece ASO"}
        else:
            conteudo = {"resumo": "ok", "campos": {}, "prioridade": "media", "motivo_prioridade": "ok",
                        "validade": {"data": None, "inicio": None, "evidencia": None}}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(conteudo)}}]})

    cli = ClienteOpenAICompat("http://falso/v1", "modelo-x", "k", multimodal=False, timeout=5)
    cli.http = httpx.Client(transport=httpx.MockTransport(responder))
    return cli


@pytest.fixture()
def lote_com_ia(lote_terceiros, monkeypatch):
    from app import worker
    from app.config import settings
    from app.pipeline import orquestrador, resumir

    c, _ = lote_terceiros
    cli = _cliente_falso()
    monkeypatch.setattr(orquestrador, "obter_llm", lambda: cli)
    monkeypatch.setattr(resumir, "obter_llm", lambda: cli)
    monkeypatch.setattr(settings, "LLM_SEMPRE", True)
    caminho = os.path.join(TMP, "terceiros_ia.pdf")
    subprocess.run([sys.executable, os.path.join(BASE, "scripts", "gerar_lote_bernhoeft.py"), caminho], check=True)
    with open(caminho, "ab") as f:          # outro hash (o upload recusa arquivo repetido)
        f.write(b"\n% copia com IA\n")
    with open(caminho, "rb") as f:
        r = c.post("/lotes", files={"arquivo": ("terceiros_ia.pdf", f, "application/pdf")})
    assert r.status_code == 201, r.text
    worker.rodar(uma_vez=True)
    yield c, r.json()["id"]
    monkeypatch.undo()
    worker.rodar(uma_vez=True)                       # termina o reprocessamento do teste antes de apagar
    assert c.delete(f"/lotes/{r.json()['id']}").status_code == 200   # não contamina os outros testes


def test_com_llm_conta_paginas_e_explica(lote_com_ia):
    c, lote_id = lote_com_ia
    paginas = c.get(f"/lotes/{lote_id}/paginas").json()
    nao_brancas = sum(1 for p in paginas if not p.get("em_branco"))
    ia = c.get(f"/lotes/{lote_id}").json()["ia"]
    assert ia["chamadas_classificacao"] == nao_brancas == ia["paginas_com_ia"]
    assert ia["chamadas_resumo"] == len(c.get(f"/lotes/{lote_id}/documentos").json())
    assert ia["percentual_paginas_com_ia"] == round(100 * nao_brancas / ia["paginas_total"], 1)
    docs = c.get(f"/lotes/{lote_id}/documentos").json()
    assert all(d["decidido_por"] in ("ia", "combinado") and d["ia_justificativa"] for d in docs)

    # revisão humana que muda o tipo marca "humano"
    alvo = docs[0]
    novo_tipo = "CTPS" if alvo["tipo"] != "CTPS" else "ASO"
    r = c.post(f"/documentos/{alvo['id']}/revisao", json={"acao": "alterar_tipo", "tipo": novo_tipo})
    assert r.status_code == 200, r.text
    assert c.get(f"/documentos/{alvo['id']}").json()["decidido_por"] == "humano"

    # reprocessar zera os contadores (o contador reflete a última execução)
    r = c.post(f"/lotes/{lote_id}/reprocessar", params={"tudo": "true"})
    assert r.status_code == 200, r.text
    ia = r.json()["ia"]
    assert ia["chamadas_total"] == 0 and ia["paginas_com_ia"] == 0
