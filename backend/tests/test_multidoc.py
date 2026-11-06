"""F8: várias folhas numa mesma imagem → uma página por folha; nenhuma divisão falsa nos lotes normais."""
import io
import os
import sys

import cv2
import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFont

from app.pipeline import multidoc
from tests.conftest import BASE

sys.path.insert(0, os.path.join(BASE, "scripts"))
import gerar_duas_folhas  # noqa: E402
from gerar_lote_teste import FONTE  # noqa: E402


def _bgr(img: Image.Image):
    return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def _png(img: Image.Image) -> bytes:
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


def _mesa_com_folhas(caixas, largura=2480, altura=3508):
    mesa = Image.new("RGB", (largura, altura), (60, 60, 60))
    d = ImageDraw.Draw(mesa)
    fonte = ImageFont.truetype(FONTE, 48)
    for x0, y0, x1, y1 in caixas:
        d.rectangle((x0, y0, x1, y1), fill=(250, 250, 250))
        for k in range(6):
            d.text((x0 + 60, y0 + 80 + k * 110), f"Documento de teste, linha {k}", font=fonte, fill=(20, 20, 20))
    return mesa


def test_duas_folhas_em_ordem_de_leitura():
    img = _mesa_com_folhas([(150, 1850, 2330, 3300), (150, 200, 2330, 1650)])
    escala = 2480 / 1240
    pequena = cv2.resize(_bgr(img), (1240, 1754))
    caixas = multidoc.detectar_recortes(pequena)
    assert len(caixas) == 2
    assert caixas[0][1] < caixas[1][1]                       # a de cima primeiro
    assert abs(caixas[0][1] * escala - 200) < 80


def test_lado_a_lado_esquerda_para_direita():
    caixas = multidoc.detectar_recortes(_bgr(_mesa_com_folhas([(1300, 300, 2300, 1900), (150, 300, 1150, 1900)],
                                                              altura=2300)))
    assert len(caixas) == 2 and caixas[0][0] < caixas[1][0]


def test_folha_unica_grande_nao_divide():
    assert multidoc.detectar_recortes(_bgr(_mesa_com_folhas([(40, 40, 2440, 3468)]))) == []


def test_uma_folha_pequena_nao_divide():
    assert multidoc.detectar_recortes(_bgr(_mesa_com_folhas([(800, 1200, 1700, 2400)]))) == []


def test_folha_inclinada_e_endireitada():
    mesa = Image.new("RGB", (2480, 3508), (60, 60, 60))
    retrato = gerar_duas_folhas.folha(900, 1270, "ATESTADO", ["linha 1", "linha 2", "linha 3"])
    girada = retrato.rotate(5, expand=True, fillcolor=(60, 60, 60))
    mesa.paste(girada, (150, 200))
    mesa.paste(gerar_duas_folhas.folha(900, 1270, "CONTRATO", ["a", "b", "c"]), (1400, 2000))
    png = _png(mesa)
    escala = 2480 / 1240
    regioes = multidoc.detectar_regioes(cv2.resize(_bgr(mesa), (1240, 1754)))
    assert len(regioes) == 2
    rec = multidoc.recortar(png, regioes, escala)
    h, w = cv2.imdecode(np.frombuffer(rec[0].png, np.uint8), cv2.IMREAD_COLOR).shape[:2]
    assert h > w and abs(w - 900) < 90 and abs(h - 1270) < 120      # retrato, sem a "cunha" da inclinação


def test_normalizar_imagem_com_duas_folhas():
    r = multidoc.normalizar_arquivo(_png(gerar_duas_folhas.gerar()), "foto.png")
    assert r is not None
    pdf, info = r
    assert info == [{"pagina_original": 0, "recortes": 2}] and pymupdf.open(stream=pdf, filetype="pdf").page_count == 2


def test_lotes_normais_nao_sao_divididos(lote_pdf):
    """Regressão obrigatória: nenhuma divisão falsa no lote de teste nem no de terceiros."""
    import subprocess
    from tests.conftest import TMP
    terceiros = os.path.join(TMP, "multidoc_terceiros.pdf")
    subprocess.run([sys.executable, os.path.join(BASE, "scripts", "gerar_lote_bernhoeft.py"), terceiros], check=True)
    for caminho in (lote_pdf, terceiros):
        with open(caminho, "rb") as f:
            assert multidoc.normalizar_arquivo(f.read(), "lote.pdf") is None


def test_erro_interno_segue_com_o_original(monkeypatch):
    def explode(*a):
        raise RuntimeError("falha simulada")
    monkeypatch.setattr(multidoc, "_normalizar", explode)
    assert multidoc.normalizar_arquivo(b"qualquer", "x.png") is None


def test_upload_de_foto_com_duas_folhas(processado):
    from app import worker
    c, _ = processado
    r = c.post("/lotes", files={"arquivo": ("duas_folhas.png", _png(gerar_duas_folhas.gerar()), "image/png")})
    assert r.status_code == 201, r.text
    lote = r.json()
    assert lote["total_paginas"] == 2 and lote["multidoc"] == [{"pagina_original": 0, "recortes": 2}]
    worker.rodar(uma_vez=True)
    docs = c.get(f"/lotes/{lote['id']}/documentos").json()
    assert len(docs) == 2
    assert c.delete(f"/lotes/{lote['id']}").status_code == 200
