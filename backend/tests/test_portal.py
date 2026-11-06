"""F7: portal do fornecedor — token secreto, 404 sem oráculo, veredito em lista branca, limites."""
import hashlib
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone

import pytest

from app.config import settings
from app.db import SessionLocal
from app.models import ConviteFornecedor, Documento
from app.pipeline import veredito_portal as vp
from tests.conftest import BASE, TMP

PROIBIDAS = {"alertas", "risco", "texto", "cpf", "cpf_mascarado", "motivos", "resumo", "erro"}
EXIGIDOS = ["CND_FEDERAL", "CRF_FGTS", "CNDT", "CONTRATO", "NOTA_FISCAL"]


def _chaves(obj) -> set[str]:
    if isinstance(obj, dict):
        return set(obj) | set().union(*(_chaves(v) for v in obj.values()))
    if isinstance(obj, list):
        return set().union(*(_chaves(v) for v in obj)) if obj else set()
    return set()


@pytest.fixture()
def convite(lote_terceiros):
    c, _ = lote_terceiros
    criados, lotes = [], []

    def criar(**kw):
        corpo = {"fornecedor_nome": "Construtora Exemplo LTDA", "exigidos": EXIGIDOS} | kw
        r = c.post("/portal/convites", json=corpo)
        assert r.status_code == 201, r.text
        criados.append(r.json()["id"])
        return r.json()

    yield c, criar, lotes
    for lote_id in lotes:
        c.delete(f"/lotes/{lote_id}")
    with SessionLocal() as db:
        db.query(ConviteFornecedor).filter(ConviteFornecedor.id.in_(criados)).delete()
        db.commit()


def test_token_so_na_criacao_e_hash_no_banco(convite):
    c, criar, _ = convite
    r = criar()
    assert r["url"].endswith(f"/portal/{r['token']}") and len(r["token"]) >= 40
    lista = c.get("/portal/convites").json()
    assert lista and all("token" not in x and "token_hash" not in x for x in lista)
    with SessionLocal() as db:
        guardado = db.get(ConviteFornecedor, r["id"])
        assert guardado.token_hash == hashlib.sha256(r["token"].encode()).hexdigest()
    p = c.get(f"/portal/{r['token']}").json()
    assert p["fornecedor"] == "Construtora Exemplo LTDA" and all(s["situacao"] == "nao_enviado" for s in p["situacao"])
    assert c.post("/portal/convites", json={"fornecedor_nome": "X Y", "exigidos": ["INVENTADO"]}).status_code == 422


def test_link_invalido_sempre_igual(convite):
    c, criar, _ = convite
    errado = c.get("/portal/token-que-nao-existe")
    assert errado.status_code == 404
    revogado, expirado, esgotado = criar(), criar(), criar(usos_max=1)
    c.post(f"/portal/convites/{revogado['id']}/revogar")
    with SessionLocal() as db:
        db.get(ConviteFornecedor, expirado["id"]).expira_em = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.get(ConviteFornecedor, esgotado["id"]).usos = 1
        db.commit()
    for conv in (revogado, expirado, esgotado):
        r = c.get(f"/portal/{conv['token']}")
        assert r.status_code == 404 and r.json() == errado.json()


def _pdf_bernhoeft(sufixo: str) -> str:
    caminho = os.path.join(TMP, f"portal_{sufixo}.pdf")
    subprocess.run([sys.executable, os.path.join(BASE, "scripts", "gerar_lote_bernhoeft.py"), caminho], check=True)
    with open(caminho, "ab") as f:
        f.write(f"\n% portal {sufixo}\n".encode())
    return caminho


def _enviar(c, token, caminho, nome=None):
    with open(caminho, "rb") as f:
        return c.post(f"/portal/{token}/enviar", files={"arquivo": (nome or os.path.basename(caminho), f, "application/pdf")})


def test_envio_e_veredito(convite):
    from app import worker
    c, criar, lotes = convite
    conv = criar()
    r = _enviar(c, conv["token"], _pdf_bernhoeft("a"))
    assert r.status_code == 201, r.text
    envio = r.json()["envio_id"]
    lotes.append(envio)
    assert c.get(f"/lotes/{envio}").json()["origem"] == "portal"
    worker.rodar(uma_vez=True)

    e = c.get(f"/portal/{conv['token']}/envios/{envio}").json()
    assert e["status"] == "concluido" and e["progresso"] == 1.0
    assert not (_chaves(e) & PROIBIDAS), _chaves(e) & PROIBIDAS
    sit = {s["tipo"]: s for s in e["situacao"]}
    crf_venc = (date.today() - timedelta(days=5)).strftime("%d/%m/%Y")
    assert sit["CRF_FGTS"]["situacao"] == "reprovado"
    assert sit["CRF_FGTS"]["motivo"] == f"Documento vencido em {crf_venc}. Envie a versão atualizada."
    assert sit["NOTA_FISCAL"]["situacao"] == "nao_enviado"
    # conteúdo idêntico a outro lote (risco "atenção"): o fornecedor só vê a mensagem neutra
    em_analise = [d for d in e["documentos"] if d["veredito"] == "em_analise"]
    assert em_analise and all(d["motivo"] == vp.MSG_EM_ANALISE and "fraude" not in d["motivo"] for d in em_analise)

    # o revisor aprova a CNDT: "em análise" some e aparece o aviso de vencimento próximo
    cndt = next(d for d in c.get(f"/lotes/{envio}/documentos").json() if d["tipo"] == "CNDT")
    assert c.post(f"/documentos/{cndt['id']}/revisao", json={"acao": "aprovar"}).status_code == 200
    sit = {s["tipo"]: s for s in c.get(f"/portal/{conv['token']}").json()["situacao"]}
    assert sit["CNDT"]["situacao"] == "aprovado" and sit["CNDT"]["aviso"].startswith("Válido, mas vence em")

    # outro convite não enxerga este envio; mesmo arquivo por outro fornecedor → 409 genérico
    outro = criar(fornecedor_nome="Outra Empresa")
    assert c.get(f"/portal/{outro['token']}/envios/{envio}").status_code == 404
    assert c.get(f"/portal/convites/{conv['id']}/envios").json()[0]["lote_id"] == envio
    with SessionLocal() as db:
        assert db.get(ConviteFornecedor, conv["id"]).usos == 1


def test_limites(convite, monkeypatch):
    c, criar, _ = convite
    conv = criar()
    lixo = os.path.join(TMP, "falso.pdf")
    with open(lixo, "wb") as f:
        f.write(b"isto nao e um pdf" * 10)
    assert _enviar(c, conv["token"], lixo).status_code == 415                     # assinatura não confere
    assert _enviar(c, conv["token"], lixo, nome="virus.exe").status_code == 415   # extensão proibida
    monkeypatch.setattr(settings, "PORTAL_MAX_UPLOAD_MB", 0)
    assert _enviar(c, conv["token"], lixo).status_code == 413
    with SessionLocal() as db:
        assert db.get(ConviteFornecedor, conv["id"]).usos == 0                     # recusado não gasta uso
    monkeypatch.setattr(settings, "PORTAL_MAX_ENVIOS_POR_HORA", 0)
    assert _enviar(c, conv["token"], lixo).status_code == 429


def _doc(tipo, criado, validade_dias=None, status="auto_aprovado", risco="confiavel"):
    return Documento(id=f"{tipo}{criado}", tipo=tipo, status_revisao=status, risco=risco,
                     criado_em=datetime(2026, 1, criado, tzinfo=timezone.utc),
                     validade_data=date.today() + timedelta(days=validade_dias) if validade_dias is not None else None)


def test_consolidar_reenvio_substitui():
    velho = _doc("CNDT", 1, validade_dias=-3)                 # vencido
    novo = _doc("CNDT", 2, validade_dias=150)                 # reenvio corrigido
    sit = vp.consolidar(["CNDT", "CRF_FGTS"], vp.mais_recentes_por_exigido(["CNDT", "CRF_FGTS"], [velho, novo]))
    assert sit[0]["situacao"] == "aprovado" and sit[1]["situacao"] == "nao_enviado"
    assert vp.consolidar(["CNDT"], {"CNDT": velho})[0]["situacao"] == "reprovado"
    assert vp.avaliar_documento(_doc("DESCONHECIDO", 3))["motivo"] == vp.MSG_DESCONHECIDO
