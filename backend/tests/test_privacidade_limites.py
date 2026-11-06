"""Exemplos de limitações da detecção com texto mal reconhecido pelo OCR."""
from types import SimpleNamespace

import pymupdf
import pytest

from app.pipeline import anonimizar
from app.pipeline.montar import montar_pdf
from app.storage import LocalStorage


def test_ocr_com_erros_pode_deixar_trechos_visiveis(monkeypatch):
    # Sem o reconhecedor estatístico, estas variantes documentam falsos negativos reais;
    # não representam todas as saídas possíveis de Tesseract ou do reconhecedor.
    monkeypatch.setattr(anonimizar, "_nlp", lambda: None)
    casos = [
        ("CPF: 529.982.24?-25", "529.982.24?-25"),
        ("nome: maria exemplo da silva", "maria exemplo da silva"),
        ("Endereco: Rua das Flores, I00", "Rua das Flores"),
    ]
    for texto, trecho in casos:
        mascarado, _ = anonimizar.mascarar_texto(texto)
        assert trecho in mascarado


@pytest.mark.parametrize('nativa', [True, False])
def test_tarja_remove_texto_e_cobre_imagem(tmp_path, monkeypatch, nativa):
    monkeypatch.setattr(anonimizar, '_nlp', lambda: None)
    original = pymupdf.open()
    pagina = original.new_page(width=595, height=842)
    pagina.insert_text((50, 80), 'Nome: Maria Exemplo da Silva', fontsize=14)
    pagina.insert_text((50, 115), 'CPF: 529.982.247-25', fontsize=14)
    pagina.insert_text((50, 150), 'Endereco: Rua das Flores, 100', fontsize=14)
    pagina.insert_text((50, 185), 'Documento ficticio', fontsize=14)
    palavras = [{'x0': w[0], 'y0': w[1], 'x1': w[2], 'y1': w[3], 't': w[4],
                 'c': 100, 'b': w[5], 'l': w[6]} for w in pagina.get_text('words')]
    imagem = pagina.get_pixmap(dpi=150).tobytes('png')
    caminho = tmp_path / 'original.pdf'
    original.save(caminho)
    original.close()
    storage = LocalStorage(str(tmp_path))
    storage.put_json('palavras.json', palavras)
    storage.put_bytes('imagem.png', imagem, 'image/png')
    p = SimpleNamespace(palavras_key='palavras.json', imagem_key='imagem.png', nativa=nativa,
                        numero=0, largura_pt=595, altura_pt=842)
    dados = montar_pdf(storage, str(caminho), [p], anonimizar=True)
    with pymupdf.open(stream=dados, filetype='pdf') as pdf:
        texto = pdf[0].get_text()
        assert all(t not in texto for t in ('Maria', '529.982.247-25', 'Flores'))
        assert 'ficticio' in texto
        pix = pdf[0].get_pixmap(dpi=72, colorspace=pymupdf.csRGB, alpha=False)
        for termo in ('Maria', '529.982.247-25', 'Flores,'):
            palavra = next(w for w in palavras if w['t'] == termo)
            x = int((palavra['x0'] + palavra['x1']) / 2)
            y = int((palavra['y0'] + palavra['y1']) / 2)
            assert pix.pixel(x, y) == (0, 0, 0)
