"""F6: alertas de vencimento por e-mail/WhatsApp — faixas, sem repetição, retentativa, privacidade, agendador."""
import json
import re
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.alertas import canais, servico
from app.config import settings
from app.db import SessionLocal
from app.models import AlertaEnviado, Configuracao, Documento

RX_CPF = re.compile(r"\d{3}\.\d{3}\.\d{3}-\d{2}")


@pytest.mark.parametrize("dias, faixa", [(45, None), (31, None), (30, "30"), (16, "30"), (15, "15"), (8, "15"),
                                         (7, "7"), (3, "7"), (2, "7"), (1, "1"), (0, "1"), (-1, "vencido"),
                                         (-30, "vencido")])
def test_faixa_do_documento(dias, faixa):
    assert servico.faixa_do_documento(dias, [30, 15, 7, 1]) == faixa


def test_faixas_do_env(monkeypatch):
    monkeypatch.setattr(settings, "ALERTAS_FAIXAS_DIAS", "7, 30,x,30,-2,1")
    assert settings.alertas_faixas == [1, 7, 30]


def _do_lote(c, lote_id):
    return {d["id"]: d for d in c.get(f"/lotes/{lote_id}/documentos").json()}


def test_candidatos_do_lote_bernhoeft(lote_terceiros):
    c, lote = lote_terceiros
    docs = _do_lote(c, lote["id"])
    with SessionLocal() as db:
        cands = {i["documento_id"]: i for i in servico.candidatos(db) if i["documento_id"] in docs}
    por_tipo = {}
    for i in cands.values():
        por_tipo.setdefault(i["tipo"], []).append(i["faixa"])
    assert por_tipo["CRF_FGTS"] == ["vencido"]            # venceu há 5 dias
    assert por_tipo["CNDT"] == ["30"]                     # vence em 20 dias
    assert por_tipo["CONTRATO"] == ["30"]                 # vence em ~25 dias
    assert "CND_FEDERAL" not in por_tipo                  # vence em 70 dias: fora das faixas
    assert all(i["trabalhador"] is None or "***" in i["trabalhador"] for i in cands.values())


def test_documento_substituido_nao_gera_aviso(lote_terceiros):
    c, lote = lote_terceiros
    crf = next(d for d in _do_lote(c, lote["id"]).values() if d["tipo"] == "CRF_FGTS")
    with SessionLocal() as db:
        antigo = db.get(Documento, crf["id"])
        novo = Documento(lote_id=antigo.lote_id, ordem=99, tipo="CRF_FGTS", pagina_inicio=0, pagina_fim=0,
                         confianca=0.9, status_revisao="auto_aprovado", trabalhador_id=antigo.trabalhador_id,
                         validade_data=antigo.validade_data + timedelta(days=60))
        db.add(novo)
        db.flush()
        ids = {i["documento_id"] for i in servico.candidatos(db)}
        assert crf["id"] not in ids                       # o mais recente (renovado) substitui o vencido
        db.rollback()


@pytest.fixture()
def contato(lote_terceiros):
    c, _ = lote_terceiros
    criados = []

    def criar(canal="whatsapp", destino="5581999999999"):
        r = c.post("/alertas/contatos", json={"nome": "Gestor de contratos", "canal": canal, "destino": destino})
        assert r.status_code == 201, r.text
        criados.append(r.json()["id"])
        return r.json()

    yield c, criar
    for i in criados:
        c.delete(f"/alertas/contatos/{i}")


def test_executar_simulado_nao_repete(contato):
    c, criar = contato
    criar()
    previa = c.get("/alertas/pendentes").json()
    with SessionLocal() as db:
        assert db.query(AlertaEnviado).count() == 0          # a prévia não grava nada
    assert previa and previa[0]["itens"]
    texto = previa[0]["texto"]
    assert "VENCIDOS" in texto and "CRF" in texto and not RX_CPF.search(texto)

    r = c.post("/alertas/executar", params={"simular": "true"}).json()
    assert r["mensagens"] == 1 and r["simulado"] and r["itens"] == len(previa[0]["itens"])
    assert c.post("/alertas/executar", params={"simular": "true"}).json()["mensagens"] == 0   # sem repetir
    hist = c.get("/alertas/historico").json()
    assert hist and all(h["status"] == "simulado" for h in hist)


def test_whatsapp_real_falha_e_depois_envia(contato, monkeypatch):
    c, criar = contato
    criar()
    monkeypatch.setattr(settings, "ALERTAS_MODO", "real")
    monkeypatch.setattr(settings, "EVOLUTION_URL", "http://evolution.falsa:8080/")
    monkeypatch.setattr(settings, "EVOLUTION_INSTANCIA", "minha")
    monkeypatch.setattr(settings, "EVOLUTION_APIKEY", "chave-secreta")
    pedidos, respostas = [], iter([500, 201])

    def responder(req: httpx.Request) -> httpx.Response:
        pedidos.append(req)
        return httpx.Response(next(respostas), json={})

    monkeypatch.setattr(canais, "criar_http", lambda: httpx.Client(transport=httpx.MockTransport(responder)))

    r = c.post("/alertas/executar").json()
    assert r["falhas"] == 1 and r["mensagens"] == 0
    req = pedidos[0]
    assert str(req.url) == "http://evolution.falsa:8080/message/sendText/minha"
    assert req.headers["apikey"] == "chave-secreta"
    corpo = json.loads(req.content)
    assert corpo["number"] == "5581999999999" and "Document Factory" in corpo["text"] and not RX_CPF.search(corpo["text"])
    hist = c.get("/alertas/historico").json()
    assert hist and all(h["status"] == "falhou" and "chave-secreta" not in (h["erro"] or "") for h in hist)

    r = c.post("/alertas/executar").json()                  # tenta de novo: agora deu certo
    assert r["mensagens"] == 1 and r["falhas"] == 0
    assert all(h["status"] == "enviado" for h in c.get("/alertas/historico").json())


def test_email_smtp(contato, monkeypatch):
    c, criar = contato
    criar(canal="email", destino="gestor@empresa.example")
    enviados = []

    class SMTPFalso:
        def __init__(self, host, port, timeout):
            self.host = host

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            pass

        def login(self, u, s):
            pass

        def send_message(self, msg):
            enviados.append(msg)

    monkeypatch.setattr(canais.smtplib, "SMTP", SMTPFalso)
    for k, v in {"ALERTAS_MODO": "real", "SMTP_HOST": "smtp.falso", "SMTP_REMETENTE": "alertas@df.example"}.items():
        monkeypatch.setattr(settings, k, v)
    assert c.post("/alertas/executar").json()["mensagens"] == 1
    msg = enviados[0]
    assert msg["To"] == "gestor@empresa.example" and msg["Subject"].startswith("Document Factory:")
    assert "⚠️" not in msg.get_content() and not RX_CPF.search(msg.get_content())


def test_contato_invalido(lote_terceiros):
    c, _ = lote_terceiros
    assert c.post("/alertas/contatos", json={"nome": "X", "canal": "email", "destino": "sem-arroba"}).status_code == 422
    assert c.post("/alertas/contatos", json={"nome": "Xy", "canal": "whatsapp", "destino": "(81) 9999"}).status_code == 422
    assert c.post("/alertas/contatos", json={"nome": "Xy", "canal": "sms", "destino": "1"}).status_code == 422
    cfg = c.get("/alertas/config").json()
    assert cfg["modo"] == "simulado" and "EVOLUTION_APIKEY" not in json.dumps(cfg)


def _limpar_agenda():
    with SessionLocal() as db:
        db.query(Configuracao).filter(Configuracao.chave == servico.CHAVE_ULTIMA_EXECUCAO).delete()
        db.commit()


def test_rodar_agendado_uma_vez_por_dia(contato):
    _, criar = contato
    criar()
    _limpar_agenda()
    meio_dia = datetime(2026, 11, 6, 15, 0, tzinfo=timezone.utc)          # 12h em Brasília
    madrugada = datetime(2026, 11, 7, 6, 0, tzinfo=timezone.utc)          # 3h: antes da hora de execução
    with SessionLocal() as db:
        assert servico.rodar_agendado(db, madrugada) is None
        assert servico.rodar_agendado(db, meio_dia)["mensagens"] == 1
        assert servico.rodar_agendado(db, meio_dia) is None                # 2ª vez no mesmo dia não roda
    _limpar_agenda()


def test_rodar_agendado_falha_restaura(contato, monkeypatch):
    _, criar = contato
    criar()
    _limpar_agenda()

    def explode(*a, **k):
        raise RuntimeError("SMTP caiu")

    monkeypatch.setattr(servico, "executar", explode)
    meio_dia = datetime(2026, 11, 6, 15, 0, tzinfo=timezone.utc)
    with SessionLocal() as db:
        assert servico.rodar_agendado(db, meio_dia) is None
        assert db.get(Configuracao, servico.CHAVE_ULTIMA_EXECUCAO) is None   # reserva desfeita: tenta de novo
    _limpar_agenda()


def test_canal_real_sem_configuracao():
    with pytest.raises(canais.ErroEnvio):
        canais.obter_canal("whatsapp", simular=False)
