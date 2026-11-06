"""Extras: aprender com as correções humanas e sinais de fraude com veredito explicável."""
import json
import os
import uuid
from datetime import date, timedelta

import httpx
import pymupdf

from app.db import SessionLocal
from app.llm.openai_compat import ClienteOpenAICompat
from app.models import Documento, Lote
from app.pipeline import aprendizado, fraude
from app.pipeline.classificar import classificar_por_regras


def _lote(db, **kw) -> Lote:
    lote = Lote(nome=kw.pop("nome", "teste"), arquivo_key="x", hash_sha256=uuid.uuid4().hex, mime="application/pdf",
                tamanho_bytes=1, total_paginas=0, status="concluido", **kw)
    db.add(lote)
    db.flush()
    return lote


# ------------------------------------------------------------------ aprender com as correções
def test_uma_correcao_vira_regra_e_pode_ser_desfeita(processado):
    c, _ = processado
    with SessionLocal() as db:
        lote = _lote(db)
        doc = Documento(lote_id=lote.id, ordem=0, tipo="DESCONHECIDO", pagina_inicio=0, pagina_fim=0, confianca=0.2,
                        status_revisao="pendente", titulo="DEMONSTRATIVO MENSAL DE VENCIMENTOS",
                        texto="DEMONSTRATIVO MENSAL DE VENCIMENTOS\nServidor [NOME]\nVencimento base R$ 3.000,00")
        db.add(doc)
        db.commit()
        doc_id = doc.id
    topo = "DEMONSTRATIVO MENSAL DE VENCIMENTOS Prefeitura Fictícia"
    assert classificar_por_regras("Vencimento base", topo).tipo != "CONTRACHEQUE"      # antes: não sabe

    r = c.post(f"/documentos/{doc_id}/revisao", json={"acao": "alterar_tipo", "tipo": "CONTRACHEQUE", "usuario": "ana"})
    assert r.status_code == 200
    ap = next(a for a in c.get("/aprendizados").json() if a["titulo"] == "demonstrativo mensal de vencimentos")
    assert ap["tipo_certo"] == "CONTRACHEQUE" and ap["tipo_errado"] == "DESCONHECIDO" and ap["usuario"] == "ana"

    with SessionLocal() as db:
        depois = classificar_por_regras("Vencimento base", topo, aprendizado.regras(db))
        assert depois.tipo == "CONTRACHEQUE" and depois.aprendizado_id == ap["id"]          # depois: aprendeu
        assert any(t == "CONTRACHEQUE" for t, _ in aprendizado.exemplos(db))

    assert c.post(f"/aprendizados/{ap['id']}/desativar").json()["ativo"] is False
    with SessionLocal() as db:
        assert all(i != ap["id"] for i, _, _ in aprendizado.regras(db))


def test_correcoes_vao_como_exemplo_para_o_modelo():
    corpos = []

    def responder(req):
        corpos.append(json.loads(req.read().decode())["messages"][1]["content"][0]["text"])
        return httpx.Response(200, json={"choices": [{"message": {"content":
                              '{"tipo": "CONTRACHEQUE", "inicio_documento": true, "confianca": 0.9}'}}]})

    cli = ClienteOpenAICompat("http://falso/v1", "m", "k", multimodal=False, timeout=5)
    cli.http = httpx.Client(transport=httpx.MockTransport(responder))
    r = cli.classificar("texto [CPF]", None, None, [("CONTRACHEQUE", "DEMONSTRATIVO MENSAL DE VENCIMENTOS ...")])
    assert r.tipo == "CONTRACHEQUE"
    assert "EXEMPLOS CORRIGIDOS POR REVISORES" in corpos[0] and "tipo correto CONTRACHEQUE" in corpos[0]


# ------------------------------------------------------------------ sinais de fraude
def test_pdf_editado_e_modificado(tmp_path):
    caminho = os.path.join(tmp_path, "editado.pdf")
    d = pymupdf.open()
    d.new_page()
    d.set_metadata({"producer": "Adobe Photoshop 25.0", "creationDate": "D:20260101120000",
                    "modDate": "D:20260601120000"})
    d.save(caminho)
    alertas = fraude.analisar_pdf(caminho)
    assert {a["codigo"] for a in alertas} == {"pdf_editado", "pdf_modificado"}
    assert "Photoshop" in alertas[0]["evidencia"] and fraude.veredito(alertas) == "atencao"


def test_pdf_limpo_sem_alerta(lote_pdf):
    assert fraude.analisar_pdf(lote_pdf) == []


def test_documento_repetido_em_outro_lote(lote_terceiros):
    c, lote = lote_terceiros
    original = c.get(f"/lotes/{lote['id']}/documentos").json()[0]
    with SessionLocal() as db:
        texto = db.get(Documento, original["id"]).texto
        outro = _lote(db, nome="reenvio.pdf")
        copia = Documento(lote_id=outro.id, ordem=0, tipo="ASO", pagina_inicio=0, pagina_fim=0, confianca=0.9,
                          status_revisao="auto_aprovado", texto=texto)
        db.add(copia)
        db.flush()
        fraude.aplicar(db, outro, copia, [])
        # F1: "atenção" agora também vai para a fila de revisão (antes só sinalizava)
        assert copia.risco == "atencao" and copia.status_revisao == "pendente"
        assert any(m.startswith("atenção de fraude:") for m in copia.motivos)
        assert copia.alertas[0]["codigo"] == "repetido" and "terceiros.pdf" in copia.alertas[0]["evidencia"]
        db.rollback()


def test_data_impossivel_e_alto_risco_e_vai_para_revisao():
    with SessionLocal() as db:
        lote = _lote(db)
        doc = Documento(lote_id=lote.id, ordem=0, tipo="ASO", pagina_inicio=0, pagina_fim=0, confianca=0.95,
                        status_revisao="auto_aprovado", texto="ASO",
                        validade_inicio=date.today() + timedelta(days=40), validade_data=date.today() + timedelta(days=400))
        db.add(doc)
        db.flush()
        fraude.aplicar(db, lote, doc, [])
        assert doc.risco == "alto_risco" and doc.status_revisao == "pendente"
        assert any("possível fraude" in m for m in doc.motivos)
        db.rollback()


def test_documentos_trazem_risco_e_filtro(lote_terceiros):
    c, lote = lote_terceiros
    docs = c.get(f"/lotes/{lote['id']}/documentos").json()
    assert all(d["risco"] == "confiavel" and d["alertas"] == [] for d in docs)       # lote sintético é limpo
    assert c.get("/documentos", params={"lote_id": lote["id"], "risco": "alto_risco"}).json()["total"] == 0
    assert c.get(f"/lotes/{lote['id']}").json()["alertas"] == []
