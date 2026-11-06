"""Dossiê do trabalhador (CPF só como impressão digital) e checklist de documentos exigidos."""
import json

from app.db import SessionLocal
from app.models import Pagina, Trabalhador
from app.pipeline import identidade
from app.pipeline.segmentar import PaginaInfo, segmentar


def test_cpf_valido_e_mascarado():
    assert identidade.cpf_valido("52998224725") and not identidade.cpf_valido("52998224724")
    assert identidade.cpfs_no_texto("CPF 529.982.247-25 e 111.111.111-11 e código 85800000019") == ["52998224725"]
    assert identidade.mascarado("52998224725") == "***.982.247-**"


def test_impressao_estavel_e_sem_cpf():
    with SessionLocal() as db:
        a = identidade.impressoes(db, "CPF 529.982.247-25")
        b = identidade.impressoes(db, "outro texto, mesmo CPF 52998224725")
        db.commit()
    assert a[0]["h"] == b[0]["h"] and "52998224725" not in a[0]["h"]


def test_mudanca_de_cpf_corta_documento():
    A, B = [{"h": "aaa", "m": "x"}], [{"h": "bbb", "m": "y"}]
    ps = [PaginaInfo(0, "CONTRACHEQUE", 0.9, sinais={"titulo_topo": "CONTRACHEQUE", "cpfs": A}),
          PaginaInfo(1, "CONTRACHEQUE", 0.9, sinais={"cpfs": B}),          # sem título, outra pessoa
          PaginaInfo(2, "CONTRACHEQUE", 0.9, sinais={"cpfs": B})]          # mesma pessoa: continua
    assert [d.paginas for d in segmentar(ps)] == [[0], [1, 2]]


def test_dossie_e_checklist(lote_terceiros):
    c, lote = lote_terceiros
    lista = c.get("/trabalhadores", params={"lote_id": lote["id"]}).json()
    assert lista["total"] == 2 and lista["irregulares"] == 2
    por_cpf = {t["cpf_mascarado"]: t for t in lista["itens"]}
    a, b = por_cpf["***.982.247-**"], por_cpf["***.995.350-**"]
    assert a["documentos"] == 4 and b["documentos"] == 3
    assert set(a["faltando"]) == {"IDENTIDADE", "CTPS"} and a["vencidos"] == 1        # ASO vencido
    assert set(b["faltando"]) == {"IDENTIDADE", "FICHA_EPI"} and b["vencendo"] == 1    # NR-10 vencendo

    d = c.get(f"/trabalhadores/{a['id']}/dossie").json()
    status = {i["tipo"]: i["status"] for i in d["checklist"]}
    assert status == {"IDENTIDADE": "faltando", "CTPS": "faltando", "ASO": "vencido", "FICHA_EPI": "ok"}
    assert {doc["tipo"] for doc in d["itens"]} == {"ASO", "FICHA_EPI", "CERTIFICADO_NR", "CONTRACHEQUE"}
    assert all(doc["trabalhador"]["id"] == a["id"] for doc in d["itens"])

    db_b = c.get(f"/trabalhadores/{b['id']}/dossie").json()
    assert [x["tipo"] for x in db_b["outros_alertas"]] == ["CERTIFICADO_NR"]
    assert c.get("/trabalhadores/999999/dossie").status_code == 404


def test_cpf_nunca_guardado(lote_terceiros):
    c, lote = lote_terceiros
    corpo = json.dumps(c.get(f"/lotes/{lote['id']}/documentos").json()) + \
        json.dumps(c.get(f"/lotes/{lote['id']}/paginas").json()) + json.dumps(c.get("/trabalhadores").json())
    assert "529.982.247-25" not in corpo and "52998224725" not in corpo
    with SessionLocal() as db:
        for p in db.query(Pagina).filter(Pagina.lote_id == lote["id"]):
            assert "529.982.247-25" not in (p.texto or "") + json.dumps(p.sinais or {})
        assert all(len(t.cpf_hash) == 32 for t in db.query(Trabalhador))


def test_contrato_e_nota_nao_criam_dossie(processado):
    c, lote = processado
    docs = c.get(f"/lotes/{lote['id']}/documentos").json()
    por_tipo = {d["tipo"]: d for d in docs}
    assert por_tipo["NOTA_FISCAL"]["trabalhador"] is None          # CPF do cliente, não de trabalhador
    assert all(d["trabalhador"] is None for d in docs if d["tipo"] == "CONTRATO")
    assert por_tipo["IDENTIDADE"]["trabalhador"] is not None        # RG é documento da pessoa


def test_empresa_sem_trabalhador_e_painel(lote_terceiros):
    c, lote = lote_terceiros
    docs = c.get(f"/lotes/{lote['id']}/documentos").json()
    empresa = [d for d in docs if d["tipo"] in ("CND_FEDERAL", "CRF_FGTS", "CNDT", "CONTRATO", "GUIA_FGTS")]
    assert empresa and all(d["trabalhador"] is None for d in empresa)
    p = c.get("/painel").json()
    assert p["trabalhadores_irregulares"] >= 2 and any(a["tipo"] == "trabalhadores_irregulares" for a in p["atencao"])
