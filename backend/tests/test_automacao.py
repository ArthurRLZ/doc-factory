"""Meta de automação: limiar em tempo real, curva e acurácia medida pelas revisões."""
import uuid

from app.db import SessionLocal
from app.models import Documento, Lote, Revisao
from app.pipeline import automacao


def test_curva_e_monotonica(lote_terceiros):
    c, _ = lote_terceiros
    r = c.get("/automacao").json()
    pts = r["curva"]
    assert any(p["atual"] for p in pts)
    automaticos = [p["automaticos"] for p in pts]
    assert automaticos == sorted(automaticos, reverse=True)       # limiar maior → menos automação
    assert all(p["automaticos"] + p["para_revisao"] == r["documentos"] for p in pts)


def test_mudar_limiar_reavalia_a_fila(lote_terceiros):
    c, lote = lote_terceiros
    antes = c.get("/revisao/fila", params={"lote_id": lote["id"]}).json()
    r = c.put("/automacao/limiar", json={"limiar": 0.99}).json()
    depois = c.get("/revisao/fila", params={"lote_id": lote["id"]}).json()
    assert len(depois) >= len(antes) and r["curva"]["limiar_atual"] == 0.99
    assert all(d["motivos"] for d in depois)                       # todo pendente diz por quê
    c.put("/automacao/limiar", json={"limiar": 0.80})              # volta ao padrão dos testes
    finais = c.get("/revisao/fila", params={"lote_id": lote["id"]}).json()
    assert len(finais) == len(antes)
    # documentos bloqueados por motivo próprio (vencido sem data, tipo desconhecido...) continuam na fila
    assert c.put("/automacao/limiar", json={"limiar": 1.5}).status_code == 422


def test_acuracia_medida_pelas_revisoes(processado):
    _c, _ = processado
    with SessionLocal() as db:
        lote = Lote(nome="gabarito", arquivo_key="x", hash_sha256=uuid.uuid4().hex, mime="application/pdf",
                    tamanho_bytes=1, total_paginas=0, status="concluido")
        db.add(lote)
        db.flush()
        # 6 documentos de confiança alta aprovados (acertos) e 2 de confiança baixa corrigidos (erros)
        for i, (conf, acao) in enumerate([(0.95, "aprovar")] * 6 + [(0.55, "alterar_tipo")] * 2):
            d = Documento(lote_id=lote.id, ordem=i, tipo="CONTRATO", pagina_inicio=i, pagina_fim=i,
                          confianca=conf, status_revisao="revisado")
            db.add(d)
            db.flush()
            db.add(Revisao(documento_id=d.id, lote_id=lote.id, usuario="t", acao=acao))
        db.commit()
        c = automacao.curva(db)
        ponto = {p["limiar"]: p for p in c["curva"]}
        assert ponto[0.9]["acuracia_estimada"] == 100.0             # só os de 0.95 passariam sozinhos
        assert c["acuracia_medida"]["documentos_revisados"] >= 8
        sug = automacao.sugerir(db, 99.0)
        assert sug["limiar_sugerido"] is not None and sug["limiar_sugerido"] > 0.55
