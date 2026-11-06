"""Páginas com pouco conteúdo não podem desaparecer silenciosamente."""
import io

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app import worker
from app.main import app
from app.pipeline import ocr


def png(img):
    out = io.BytesIO()
    img.save(out, 'PNG')
    return out.getvalue()


def test_conteudo_esparso_usa_ocr_e_preserva_coordenadas(monkeypatch):
    img = Image.new('L', (2000, 2000), 255)
    ImageDraw.Draw(img).rectangle((1000, 1200, 1019, 1209), fill=0)
    tamanhos = []

    def reconhecer(corte, **_):
        tamanhos.append(corte.size)
        return {'text': ['teste'], 'conf': ['90'], 'left': [24], 'top': [24],
                'width': [20], 'height': [10], 'block_num': [1], 'par_num': [1], 'line_num': [1]}

    monkeypatch.setattr(ocr.pytesseract, 'image_to_data', reconhecer)
    resultado = ocr.ocr_png(png(img), dpi=72)
    assert resultado.texto == 'teste'
    assert tamanhos[0][0] < 2000 and tamanhos[0][1] < 2000
    assert resultado.palavras[0]['x0'] == 1000 and resultado.palavras[0]['y0'] == 1200
    assert not ocr.e_pagina_em_branco(len(resultado.palavras), resultado.tinta)


def test_lote_sem_texto_vai_para_revisao():
    imagem = png(Image.new('RGB', (500, 500), 'white'))
    with TestClient(app) as cliente:
        resposta = cliente.post('/lotes', files={'arquivo': ('sem-texto.png', imagem, 'image/png')})
        assert resposta.status_code == 201, resposta.text
        lote_id = resposta.json()['id']
        worker.rodar(uma_vez=True)
        documentos = cliente.get(f'/lotes/{lote_id}/documentos').json()
        assert len(documentos) == 1
        assert documentos[0]['status_revisao'] == 'pendente'
        assert any('Nenhum texto identificado' in motivo for motivo in documentos[0]['motivos'])


def test_ruido_esparso_distribuido_e_assinalado():
    img = Image.new('L', (1000, 1000), 255)
    img.putpixel((1, 1), 0)
    img.putpixel((998, 998), 0)
    resultado = ocr.ocr_png(png(img), dpi=72)
    assert resultado.conteudo_incerto
    assert not resultado.palavras
