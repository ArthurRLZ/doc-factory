"""Etapa 1 — PyMuPDF: abre o lote (PDF ou imagem multipágina) e rasteriza página a página.

O PyMuPDF abre PDF, TIFF multipágina, PNG, JPG... com a mesma API.
Nunca carregamos o lote inteiro na memória: renderizamos UMA página por vez.
"""
import math
from dataclasses import dataclass
from threading import Lock

import pymupdf

from app.config import settings

# Cache do último documento aberto: o worker processa páginas do mesmo lote em
# sequência, então reabrir um PDF de 500 páginas a cada página seria desperdício.
_cache: dict[str, pymupdf.Document] = {}
_lock = Lock()


def _abrir(caminho: str) -> pymupdf.Document:
    with _lock:
        if caminho not in _cache:
            for d in _cache.values():
                d.close()
            _cache.clear()
            _cache[caminho] = pymupdf.open(caminho)
        return _cache[caminho]


def fechar(caminho: str) -> None:
    """Fecha o arquivo se estiver aberto no cache (antes de apagá-lo)."""
    with _lock:
        d = _cache.pop(caminho, None)
        if d:
            d.close()


def contar_paginas(caminho: str) -> int:
    """Também serve de validação: arquivo corrompido levanta exceção aqui."""
    with pymupdf.open(caminho) as doc:
        if doc.needs_pass:
            raise ValueError("PDF protegido por senha")
        return doc.page_count


@dataclass
class PaginaRenderizada:
    png: bytes                 # imagem em DPI_OCR, tons de cinza
    thumb_jpg: bytes           # miniatura para o front
    largura_pt: float          # tamanho em pontos PDF (1/72")
    altura_pt: float
    nativa: bool               # True = PDF digital com camada de texto
    palavras_nativas: list[dict] | None
    texto_nativo: str | None
    dpi: int = 300             # DPI realmente usado (menor em páginas gigantes)


def renderizar(caminho: str, numero: int) -> PaginaRenderizada:
    doc = _abrir(caminho)
    page = doc[numero]
    rect = page.rect

    # PDF "nascido digital": já tem texto, não precisa de OCR (mais rápido e 100% preciso)
    nativa, palavras, texto = False, None, None
    if doc.is_pdf:
        texto = page.get_text("text")
        if len(texto.strip()) >= settings.TEXTO_NATIVO_MIN_CHARS:
            nativa = True
            palavras = [
                {"x0": w[0], "y0": w[1], "x1": w[2], "y1": w[3], "t": w[4], "c": 100.0,
                 "b": w[5], "l": w[6]}
                for w in page.get_text("words")
            ]
        else:
            texto = None

    dpi = dpi_seguro(rect.width, rect.height, settings.DPI_OCR, settings.MAX_MEGAPIXELS_PAGINA)
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, alpha=False)
    png = pix.tobytes("png")
    thumb_dpi = dpi_seguro(rect.width, rect.height, settings.DPI_THUMB, 1.0)
    thumb = page.get_pixmap(dpi=thumb_dpi, alpha=False).tobytes("jpg", jpg_quality=70)

    return PaginaRenderizada(png=png, thumb_jpg=thumb, largura_pt=rect.width, altura_pt=rect.height,
                             nativa=nativa, palavras_nativas=palavras, texto_nativo=texto, dpi=dpi)


def dpi_seguro(largura_pt: float, altura_pt: float, dpi: int, max_megapixels: float) -> int:
    """Reduz o DPI de páginas gigantes (ex.: planta de 2 m) para a imagem caber na memória.
    Uma página A4 a 300 dpi tem ~8,7 megapixels; o limite padrão é 60."""
    pixels = (largura_pt / 72 * dpi) * (altura_pt / 72 * dpi)
    if pixels <= max_megapixels * 1e6:
        return dpi
    return max(10, int(dpi * math.sqrt(max_megapixels * 1e6 / pixels)))
