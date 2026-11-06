"""F4: regras de separação escritas em português (interpretação, validação, efeito na segmentação, API)."""
import json
import os
import subprocess
import sys

import httpx
import pytest

from app.pipeline import regras_separacao as rs
from app.pipeline.segmentar import PaginaInfo, segmentar
from tests.conftest import BASE, TMP


# ---------------------------------------------------------------- interpretação por palavras-chave
@pytest.mark.parametrize("frase, esperado", [
    ("mantenha o contrato inteiro junto", [{"op": "manter_junto", "tipos": ["CONTRATO"]}]),
    ("MANTENHA O CONTRATO INTEIRO JUNTO", [{"op": "manter_junto", "tipos": ["CONTRATO"]}]),
    ("não divida o contrato", [{"op": "manter_junto", "tipos": ["CONTRATO"]}]),
    ("cada guia do FGTS é um documento separado", [{"op": "separar_por_pagina", "tipos": ["GUIA_FGTS"]}]),
    ("Separe cada holerite", [{"op": "separar_por_pagina", "tipos": ["CONTRACHEQUE"]}]),
    ("página em branco não separa documentos", [{"op": "branco_nao_separa"}]),
    ("Página em BRANCA nunca fecha o documento", [{"op": "branco_nao_separa"}]),
    ("o comprovante de residência fica junto do documento anterior",
     [{"op": "anexar_ao_anterior", "tipos": ["COMPROVANTE_RESIDENCIA"]}]),
    ("bom dia, tudo certo por aí?", []),
])
def test_interpretar_por_palavras(frase, esperado):
    assert rs.interpretar_por_palavras(frase) == esperado


def test_varias_frases_de_uma_vez():
    r = rs.interpretar_por_palavras("Mantenha o contrato junto. Cada guia do FGTS é um documento separado")
    assert [x["op"] for x in r] == ["manter_junto", "separar_por_pagina"]


def test_validar_descarta_lixo():
    bruto = [{"op": "apagar_tudo"}, {"op": "manter_junto", "tipos": ["INVENTADO"]},
             {"op": "manter_junto", "tipos": ["CONTRATO", "INVENTADO"]}, {"op": "manter_junto", "tipos": ["CONTRATO"]},
             {"op": "branco_nao_separa", "tipos": ["X"]}, "texto solto"]
    assert rs.validar(bruto) == [{"op": "manter_junto", "tipos": ["CONTRATO"]}, {"op": "branco_nao_separa"}]
    assert rs.validar(None) == []


# ---------------------------------------------------------------- efeito na segmentação (PaginaInfo sintéticas)
def P(n, tipo, titulo=None, x=None, branco=False, cpf=None):
    sinais = {"titulo_topo": titulo} if titulo else {}
    if x is not None:
        sinais["pagina_x"] = x
    if cpf:
        sinais["cpfs"] = [{"h": cpf}]
    return PaginaInfo(numero=n, tipo=tipo, conf_tipo=0.9, em_branco=branco, sinais=sinais)


def _grupos(docs):
    return [d.paginas for d in docs]


JUNTO = [{"op": "manter_junto", "tipos": ["CONTRATO"], "texto": "mantenha o contrato inteiro junto"}]


def test_manter_junto_nao_parte_o_contrato():
    # a pág. 2 repete o título e o OCR não reconheceu o tipo
    pags = [P(0, "CONTRATO", "CONTRATO"), P(1, "DESCONHECIDO", "CONTRATO"), P(2, "CONTRATO")]
    assert _grupos(segmentar(pags)) == [[0], [1, 2]]                       # sem regra: parte em dois
    docs = segmentar(pags, regras=JUNTO)
    assert _grupos(docs) == [[0, 1, 2]]
    assert docs[0].regras_aplicadas == ["mantenha o contrato inteiro junto"]


def test_manter_junto_respeita_pagina_1_de_n():
    pags = [P(0, "CONTRATO", "CONTRATO", x=1), P(1, "CONTRATO", x=1)]
    assert _grupos(segmentar(pags, regras=JUNTO)) == [[0], [1]]


def test_separar_por_pagina():
    pags = [P(0, "GUIA_FGTS", "GUIA"), P(1, "GUIA_FGTS")]
    assert _grupos(segmentar(pags)) == [[0, 1]]
    assert _grupos(segmentar(pags, regras=[{"op": "separar_por_pagina", "tipos": ["GUIA_FGTS"]}])) == [[0], [1]]
    # documento que se declara multipágina ("Página 2 de 2") é respeitado
    pags[1].sinais["pagina_x"] = 2
    assert _grupos(segmentar(pags, regras=[{"op": "separar_por_pagina", "tipos": ["GUIA_FGTS"]}])) == [[0, 1]]


def test_anexar_ao_anterior():
    pags = [P(0, "IDENTIDADE", "RG"), P(1, "COMPROVANTE_RESIDENCIA", "CONTA DE LUZ")]
    assert _grupos(segmentar(pags)) == [[0], [1]]
    regra = [{"op": "anexar_ao_anterior", "tipos": ["COMPROVANTE_RESIDENCIA"]}]
    assert _grupos(segmentar(pags, regras=regra)) == [[0, 1]]
    assert _grupos(segmentar(pags[1:], regras=regra)) == [[1]]               # sem documento antes: início normal


def test_branco_nao_separa():
    pags = [P(0, "CONTRATO", "CONTRATO"), P(1, "DESCONHECIDO", branco=True), P(2, "CONTRATO")]
    assert _grupos(segmentar(pags)) == [[0], [2]]
    assert _grupos(segmentar(pags, regras=[{"op": "branco_nao_separa"}])) == [[0, 2]]   # o branco é descartado


def test_regra_de_juntar_nao_passa_por_cima_de_outro_cpf():
    pags = [P(0, "ASO", "ASO", cpf="a"), P(1, "ASO", cpf="b")]
    assert _grupos(segmentar(pags, regras=[{"op": "manter_junto", "tipos": ["ASO"]}])) == [[0], [1]]


# ---------------------------------------------------------------- API
def _cliente_llm(regras):
    from app.llm.openai_compat import ClienteOpenAICompat

    def responder(req):
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"regras": regras})}}]})

    cli = ClienteOpenAICompat("http://falso/v1", "m", "k", multimodal=False, timeout=5)
    cli.http = httpx.Client(transport=httpx.MockTransport(responder))
    return cli


def test_api_interpretar_sem_llm(processado):
    c, _ = processado
    r = c.post("/regras-separacao/interpretar", json={"texto": "mantenha o contrato inteiro junto"})
    assert r.status_code == 200 and r.json()["interpretada_por"] == "palavras_chave"
    assert r.json()["regras"] == [{"op": "manter_junto", "tipos": ["CONTRATO"], "descricao": "Manter junto: Contrato"}]
    r = c.post("/regras-separacao/interpretar", json={"texto": "qual é a previsão do tempo?"})
    assert r.status_code == 422 and r.json()["exemplos"]
    assert c.get("/regras-separacao").json() == []                        # interpretar não grava


def test_api_interpretar_com_llm(processado, monkeypatch):
    from app.api import regras as api_regras
    c, _ = processado
    monkeypatch.setattr(api_regras, "obter_llm",
                        lambda: _cliente_llm([{"op": "separar_por_pagina", "tipos": ["GUIA_FGTS"]},
                                              {"op": "inventada"}]))
    r = c.post("/regras-separacao/interpretar", json={"texto": "uma guia por documento"}).json()
    assert r["interpretada_por"] == "ia" and [x["op"] for x in r["regras"]] == ["separar_por_pagina"]


def test_snapshot_no_lote_e_reprocessar(processado):
    from app import worker
    c, _ = processado
    r = c.post("/regras-separacao", json={"texto": "mantenha o contrato inteiro junto"})
    assert r.status_code == 201
    regra_id = r.json()["id"]
    try:
        caminho = os.path.join(TMP, "terceiros_regra.pdf")
        subprocess.run([sys.executable, os.path.join(BASE, "scripts", "gerar_lote_bernhoeft.py"), caminho], check=True)
        with open(caminho, "ab") as f:
            f.write(b"\n% com regra\n")
        with open(caminho, "rb") as f:
            lote = c.post("/lotes", files={"arquivo": ("terceiros_regra.pdf", f, "application/pdf")},
                          data={"regras": "cada guia do FGTS é um documento separado"}).json()
        assert [x["texto"] for x in lote["regras_aplicadas"]] == ["mantenha o contrato inteiro junto",
                                                                  "cada guia do FGTS é um documento separado"]
        worker.rodar(uma_vez=True)

        # regressão: com a regra o lote continua 100% contra o gabarito
        with open(os.path.splitext(caminho)[0] + ".gabarito.json", encoding="utf-8") as f:
            assert c.put(f"/lotes/{lote['id']}/gabarito", json=json.load(f)).status_code == 200
        m = c.get(f"/lotes/{lote['id']}/avaliacao").json()["metricas"]
        assert m["corte_f1"] == 100.0 and m["tipo_acerto_pct"] == 100.0

        # desativar a regra não muda o lote antigo; atualizar_regras troca o retrato
        c.post(f"/regras-separacao/{regra_id}/desativar")
        r = c.post(f"/lotes/{lote['id']}/reprocessar", params={"tudo": "true"}).json()
        assert len(r["regras_aplicadas"]) == 2
        worker.rodar(uma_vez=True)
        r = c.post(f"/lotes/{lote['id']}/reprocessar", params={"tudo": "true", "atualizar_regras": "true"}).json()
        assert r["regras_aplicadas"] == []
        worker.rodar(uma_vez=True)
        c.delete(f"/lotes/{lote['id']}")
    finally:
        assert c.delete(f"/regras-separacao/{regra_id}").status_code == 200
