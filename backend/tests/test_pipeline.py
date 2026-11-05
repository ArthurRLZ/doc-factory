"""Teste ponta a ponta: upload → worker → documentos → revisão → busca → PDF.

    pytest -q
"""
import pymupdf

from app.pipeline.segmentar import PaginaInfo, segmentar

# fixtures lote_pdf e processado: tests/conftest.py


def test_upload_duplicado(processado, lote_pdf):
    c, _ = processado
    with open(lote_pdf, "rb") as f:
        r = c.post("/lotes", files={"arquivo": ("lote.pdf", f, "application/pdf")})
    assert r.status_code == 409


def test_segmentacao_e_tipos(processado):
    c, lote = processado
    l = c.get(f"/lotes/{lote['id']}").json()
    assert l["status"] == "concluido" and l["progresso"] == 1.0
    docs = c.get(f"/lotes/{lote['id']}/documentos").json()
    for d in docs:
        print(d["ordem"], d["tipo"], d["pagina_inicio"] + 1, "-", d["pagina_fim"] + 1,
              d["confianca"], d["status_revisao"], d["motivos"])
    assert [d["tipo"] for d in docs] == ["CONTRATO", "IDENTIDADE", "COMPROVANTE_RESIDENCIA",
                                         "NOTA_FISCAL", "CERTIDAO", "CONTRATO"]
    assert [(d["pagina_inicio"], d["pagina_fim"]) for d in docs] == [(0, 2), (4, 4), (5, 6), (7, 7), (8, 8), (9, 10)]


def test_texto_anonimizado_e_pdf_pesquisavel(processado):
    c, lote = processado
    docs = c.get(f"/lotes/{lote['id']}/documentos").json()
    pdf = c.get(f"/documentos/{docs[0]['id']}/pdf", params={"anonimizado": False}).content
    texto = "".join(p.get_text() for p in pymupdf.open(stream=pdf, filetype="pdf"))
    assert "CONTRATANTE" in texto.upper()          # camada de texto invisível existe
    anon = c.get(f"/documentos/{docs[0]['id']}/pdf").content
    texto_anon = "".join(p.get_text() for p in pymupdf.open(stream=anon, filetype="pdf"))
    assert "123.456.789-09" not in texto_anon       # CPF removido de verdade


def test_busca(processado):
    c, _ = processado
    r = c.get("/busca", params={"q": "foro"}).json()
    assert r and all(i["tipo"] == "CONTRATO" for i in r)


def test_revisao_dividir_e_juntar(processado):
    c, lote = processado
    docs = c.get(f"/lotes/{lote['id']}/documentos").json()
    conta = next(d for d in docs if d["tipo"] == "COMPROVANTE_RESIDENCIA")
    r = c.post(f"/documentos/{conta['id']}/revisao", json={"acao": "dividir", "usuario": "teste", "pagina_corte": 6})
    assert r.status_code == 200 and len(r.json()) == 2
    assert len(c.get(f"/lotes/{lote['id']}/documentos").json()) == 7
    r = c.post(f"/documentos/{conta['id']}/revisao", json={"acao": "juntar_proximo", "usuario": "teste"})
    assert r.status_code == 200
    docs2 = c.get(f"/lotes/{lote['id']}/documentos").json()
    assert len(docs2) == 6 and [d["ordem"] for d in docs2] == list(range(6))


def test_segmentar_unitario_pagina_x_de_n():
    ps = [PaginaInfo(0, "CONTRATO", 0.9, sinais={"pagina_x": 1, "pagina_n": 2}),
          PaginaInfo(1, "NOTA_FISCAL", 0.7, sinais={"pagina_x": 2, "pagina_n": 2}),   # tipo errado, mas "2 de 2"
          PaginaInfo(2, "CONTRATO", 0.9, sinais={"pagina_x": 1, "pagina_n": 1})]
    docs = segmentar(ps)
    assert [d.paginas for d in docs] == [[0, 1], [2]]


def test_cliente_llm_com_mock():
    import httpx
    from app.llm.openai_compat import ClienteOpenAICompat

    def responder(req):
        corpo = req.read().decode()
        assert "image_url" in corpo and "[CPF]" in corpo
        return httpx.Response(200, json={"choices": [{"message": {"content":
            '```json\n{"tipo": "contrato", "inicio_documento": true, "confianca": 0.88, "justificativa": "cláusulas"}\n```'}}]})

    cli = ClienteOpenAICompat("http://falso/v1", "modelo-x", "k", multimodal=True, timeout=5)
    cli.http = httpx.Client(transport=httpx.MockTransport(responder))
    import io
    from PIL import Image
    buf = io.BytesIO(); Image.new("L", (100, 100), 255).save(buf, format="PNG")
    r = cli.classificar("CONTRATANTE [CPF]", buf.getvalue(), None)
    assert r.tipo == "CONTRATO" and r.inicio_documento is True and r.confianca == 0.88
