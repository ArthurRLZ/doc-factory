"""Etapa 1 — PyMuPDF: abre o lote (PDF ou imagem multipágina) e rasteriza página a página.

O PyMuPDF abre PDF, TIFF multipágina, PNG, JPG... com a mesma API.
Nunca carregamos o lote inteiro na memória: renderizamos UMA página por vez.
"""
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

    pix = page.get_pixmap(dpi=settings.DPI_OCR, colorspace=pymupdf.csGRAY, alpha=False)
    png = pix.tobytes("png")
    thumb = page.get_pixmap(dpi=settings.DPI_THUMB, alpha=False).tobytes("jpg", jpg_quality=70)

    return PaginaRenderizada(png=png, thumb_jpg=thumb, largura_pt=rect.width, altura_pt=rect.height,
                             nativa=nativa, palavras_nativas=palavras, texto_nativo=texto)
