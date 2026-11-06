"""Rotas das telas do front: /painel, /relatorios, filtros de /documentos, .zip do lote e formato de erro."""
import io
import json
import zipfile


def test_painel(lote_terceiros):
    c, _ = lote_terceiros
    p = c.get("/painel").json()
    cart = p["cartoes"]
    assert cart["documentos_ativos"]["valor"] >= 18                       # 6 do lote de referência + 12 de terceiros
    assert cart["vencem_semana"]["vencidos"] >= 2                          # ASO e CRF do lote de terceiros
    assert cart["aguardando_revisao"]["valor"] == p["fila_revisao"]
    assert 0 <= cart["analisados_sem_revisao"]["percentual"] <= 100
    assert len(p["volume_7_dias"]["dias"]) == 7 and p["volume_7_dias"]["dias"][-1]["rotulo"] == "Hoje"
    assert p["volume_7_dias"]["dias"][-1]["total"] == p["processados_hoje"]
    tipos_atencao = [a["tipo"] for a in p["atencao"]]
    assert "vencidos" in tipos_atencao and tipos_atencao[-1] == "processados_hoje"
    assert len(p["recentes"]) == 5 and all(r["codigo"] and r["setor"] for r in p["recentes"])
    assert sum(s["total"] for s in p["por_setor"]) == cart["documentos_ativos"]["valor"]


def test_relatorios(lote_terceiros):
    c, _ = lote_terceiros
    r = c.get("/relatorios", params={"dias": 30}).json()
    m = r["metricas"]
    assert m["documentos_processados"]["valor"] >= 18
    assert m["enviados_para_revisao"]["valor"] + round(m["concluidos_sem_revisao"]["percentual"] / 100
                                                        * m["documentos_processados"]["valor"]) \
        == m["documentos_processados"]["valor"]
    assert m["tempo_medio_analise_segundos"] is None or m["tempo_medio_analise_segundos"] >= 0
    assert [p["prioridade"] for p in r["por_prioridade"]] == ["alta", "media", "baixa"]
    assert [s["rotulo"] for s in r["status_prazos"]] == ["No prazo", "Vencem em breve", "Vencidos"]
    assert len(r["volume_diario"]) == 30


def test_documentos_filtros_da_tela(lote_terceiros):
    c, lote = lote_terceiros
    base = {"lote_id": lote["id"]}
    sst = c.get("/documentos", params=base | {"setor": "Segurança do Trabalho"}).json()
    assert sst["total"] == 5 and {d["tipo"] for d in sst["itens"]} == {"ASO", "FICHA_EPI", "CERTIFICADO_NR"}
    vencidos = c.get("/documentos", params=base | {"prazo": "vencido"}).json()["itens"]
    assert {d["tipo"] for d in vencidos} == {"ASO", "CRF_FGTS"}
    por_prazo = c.get("/documentos", params=base | {"ordenar": "prazo"}).json()["itens"]
    datas = [d["validade"]["data"] for d in por_prazo if d["validade"]["data"]]
    assert datas == sorted(datas)
    busca = c.get("/documentos", params=base | {"q": "regularidade"}).json()
    assert busca["total"] >= 1 and any(d["tipo"] == "CRF_FGTS" for d in busca["itens"])
    pag = c.get("/documentos", params=base | {"por_pagina": 5, "pagina": 3}).json()
    assert pag["total"] == 12 and pag["paginas"] == 3 and len(pag["itens"]) == 2
    assert c.get("/setores").json()


def test_zip_do_lote(lote_terceiros):
    c, lote = lote_terceiros
    r = c.get(f"/lotes/{lote['id']}/zip")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    nomes = z.namelist()
    assert "manifesto.json" in nomes and "001_aso_anon.pdf" in nomes and len(nomes) == 13
    manifesto = json.loads(z.read("manifesto.json"))
    assert len(manifesto["documentos"]) == 12 and manifesto["documentos"][0]["validade"]["status"] == "vencido"


def test_erros_num_formato_unico(processado):
    c, _ = processado
    r = c.get("/documentos/nao-existe")
    assert r.status_code == 404 and r.json()["erro"] == {"codigo": 404, "mensagem": "Documento não encontrado",
                                                         "detalhe": None}
    r = c.get("/documentos", params={"prazo": "amanha"})
    assert r.status_code == 422 and r.json()["erro"]["detalhe"][0]["campo"] == "prazo"
