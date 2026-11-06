"""F2: pré-revisão — explicação + sugestão para o revisor (IA validada; sem IA, por regras)."""
import json
import os
import subprocess
import sys

import httpx
import pytest

from app.llm.base import RespostaPreRevisao
from app.pipeline.pre_revisao import pre_revisao_por_regras, validar
from tests.conftest import BASE, TMP

TEXTO = "CARTEIRA DE TRABALHO DIGITAL\nNúmero de série 1234567\nData de admissão: 01/02/2024"


# ---------------------------------------------------------------- validação (pura)
def _r(**kw):
    base = {"explicacao": "x", "acao_sugerida": "alterar_tipo", "tipo_sugerido": "CTPS", "confianca": 0.8,
            "evidencias": ["Número de série 1234567"]}
    return RespostaPreRevisao(**(base | kw))


def test_validar_aceita_sugestao_com_evidencia():
    v = validar(_r(), TEXTO, "CONTRACHEQUE")
    assert v["acao_sugerida"] == "alterar_tipo" and v["tipo_sugerido"] == "CTPS" and v["origem"] == "ia"


def test_validar_tipo_inexistente_vira_verificar():
    v = validar(_r(tipo_sugerido="INVENTADO"), TEXTO, "CONTRACHEQUE")
    assert v["acao_sugerida"] == "verificar_manual" and v["tipo_sugerido"] is None


def test_validar_evidencia_inventada_descartada():
    v = validar(_r(evidencias=["trecho que não existe no texto"]), TEXTO, "CONTRACHEQUE")
    assert v["evidencias"] == [] and v["acao_sugerida"] == "verificar_manual"


def test_validar_tipo_igual_ao_atual_e_lixo():
    v = validar(_r(), TEXTO, "CTPS")
    assert v["tipo_sugerido"] is None and v["acao_sugerida"] == "verificar_manual"
    v = validar(_r(acao_sugerida="apagar", confianca=7, explicacao="y" * 900), TEXTO, "CTPS")
    assert v["acao_sugerida"] == "verificar_manual" and v["confianca"] == 1.0 and len(v["explicacao"]) == 400


def test_regras_sugerem_segundo_tipo_quase_empatado():
    from app.models import Documento, Pagina
    doc = Documento(tipo="CONTRACHEQUE", motivos=["confiança do tipo baixa (0,62)"])
    pag = Pagina(sinais={"scores": {"CONTRACHEQUE": 1.0, "CTPS": 0.9, "ASO": 0.1}})
    v = pre_revisao_por_regras(doc, [pag])
    assert v["acao_sugerida"] == "alterar_tipo" and v["tipo_sugerido"] == "CTPS" and v["origem"] == "regras"
    pag.sinais["scores"]["CTPS"] = 0.3
    assert pre_revisao_por_regras(doc, [pag])["acao_sugerida"] == "verificar_manual"


# ---------------------------------------------------------------- sem IA (lote compartilhado)
def test_sem_llm_pre_revisao_por_regras(lote_terceiros):
    c, lote = lote_terceiros
    docs = c.get(f"/lotes/{lote['id']}/documentos").json()
    pend = [d for d in docs if d["status_revisao"] == "pendente"]
    assert pend and all(d["pre_revisao"]["origem"] == "regras" and d["pre_revisao"]["explicacao"] for d in pend)
    assert all(d["pre_revisao"] is None for d in docs if d["status_revisao"] == "auto_aprovado")
    fila = c.get("/revisao/fila", params={"lote_id": lote["id"]}).json()
    assert all(d["pre_revisao"] for d in fila)


# ---------------------------------------------------------------- com IA simulada (MockTransport, sem rede)
class _SoPreRevisao:
    """Cliente real (MockTransport) só para a pré-revisão; classificar/resumir 'falham' e o pipeline usa regras."""

    def __init__(self):
        from app.llm.openai_compat import ClienteOpenAICompat
        conteudo = {"explicacao": "Os motivos são fracos e o texto bate com o tipo.", "acao_sugerida": "aprovar",
                    "tipo_sugerido": None, "confianca": 0.7, "evidencias": []}
        self.cli = ClienteOpenAICompat("http://falso/v1", "m", "k", multimodal=False, timeout=5)
        self.cli.http = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(conteudo)}}]})))

    def classificar(self, *a, **k):
        return None

    def resumir(self, *a, **k):
        return None

    def pre_revisar(self, *a, **k):
        return self.cli.pre_revisar(*a, **k)


@pytest.fixture()
def subir_com_ia(lote_terceiros, monkeypatch):
    from app import worker
    from app.pipeline import orquestrador, resumir
    c, _ = lote_terceiros
    fake = _SoPreRevisao()
    monkeypatch.setattr(orquestrador, "obter_llm", lambda: fake)
    monkeypatch.setattr(resumir, "obter_llm", lambda: fake)
    criados = []

    def subir(sufixo: str) -> str:
        caminho = os.path.join(TMP, f"terceiros_pre_{sufixo}.pdf")
        subprocess.run([sys.executable, os.path.join(BASE, "scripts", "gerar_lote_bernhoeft.py"), caminho], check=True)
        with open(caminho, "ab") as f:
            f.write(f"\n% {sufixo}\n".encode())
        with open(caminho, "rb") as f:
            r = c.post("/lotes", files={"arquivo": (os.path.basename(caminho), f, "application/pdf")})
        assert r.status_code == 201, r.text
        worker.rodar(uma_vez=True)
        criados.append(r.json()["id"])
        return r.json()["id"]

    yield c, subir
    for lote_id in criados:
        c.delete(f"/lotes/{lote_id}")


def test_com_llm_pendentes_recebem_sugestao_da_ia(subir_com_ia):
    c, subir = subir_com_ia
    lote_id = subir("ia")
    docs = c.get(f"/lotes/{lote_id}/documentos").json()
    pend = [d for d in docs if d["status_revisao"] == "pendente"]
    # documentos repetidos de outro lote (F1) entram na fila também: todos pendentes têm sugestão da IA
    assert pend and all(d["pre_revisao"]["origem"] == "ia" for d in pend)
    assert all(d["pre_revisao"] is None for d in docs if d["status_revisao"] == "auto_aprovado")
    assert c.get(f"/lotes/{lote_id}").json()["ia"]["chamadas_outras"] == len(pend)

    # o revisor seguiu a sugestão ("aprovar") → fica registrado e entra na estatística
    alvo = pend[0]
    assert c.post(f"/documentos/{alvo['id']}/revisao", json={"acao": "aprovar"}).status_code == 200
    rev = c.get(f"/documentos/{alvo['id']}/revisoes").json()[-1]
    assert rev["depois"]["seguiu_sugestao"] is True
    uso = c.get("/automacao").json()["pre_revisao"]
    assert uso["revisoes_com_sugestao"] >= 1 and uso["seguidas"] >= 1


def test_teto_de_chamadas_por_lote(subir_com_ia, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "PRE_REVISAO_MAX_POR_LOTE", 1)
    c, subir = subir_com_ia
    lote_id = subir("teto")
    pend = [d for d in c.get(f"/lotes/{lote_id}/documentos").json() if d["status_revisao"] == "pendente"]
    origens = [d["pre_revisao"]["origem"] for d in pend]
    assert len(pend) >= 2 and origens.count("ia") == 1 and origens.count("regras") == len(pend) - 1


def test_regerar_sob_demanda(lote_terceiros):
    c, lote = lote_terceiros
    doc = c.get(f"/lotes/{lote['id']}/documentos").json()[0]
    r = c.post(f"/documentos/{doc['id']}/pre-revisao")
    assert r.status_code == 200 and r.json()["pre_revisao"]["origem"] == "regras"
    assert c.post("/documentos/naoexiste/pre-revisao").status_code == 404
