"""Etapa 5 — PyMuPDF: monta um PDF por documento.

- PDF pesquisável: imagem da página + texto INVISÍVEL (render_mode=3) em cima,
  usando as caixas do Tesseract. Ctrl+F e copiar/colar funcionam.
- PDF anonimizado: mesmo PDF + redaction real (apaga texto E pixels da imagem).
"""
import pymupdf

from app.pipeline.anonimizar import indices_sensiveis
from app.storage import Storage

FONTE = "helv"


def _texto_invisivel(page: pymupdf.Page, palavras: list[dict]) -> None:
    for w in palavras:
        largura, altura = w["x1"] - w["x0"], w["y1"] - w["y0"]
        if largura <= 0 or altura <= 0:
            continue
        comprimento_1pt = pymupdf.get_text_length(w["t"], fontname=FONTE, fontsize=1) or 1
        fs = max(1.0, min(altura * 0.95, largura / comprimento_1pt))
        try:
            page.insert_text((w["x0"], w["y1"] - altura * 0.15), w["t"],
                             fontname=FONTE, fontsize=fs, render_mode=3)
        except Exception:
            pass  # caractere fora da fonte base: ignora a palavra, não derruba o documento


def montar_pdf(storage: Storage, caminho_original: str, paginas: list, anonimizar: bool = False) -> bytes:
    """paginas: objetos models.Pagina já processados (ordem = ordem no documento)."""
    original = pymupdf.open(caminho_original)
    out = pymupdf.open()
    try:
        for p in paginas:
            palavras = storage.get_json(p.palavras_key) if p.palavras_key else []
            if not p.imagem_key and not p.nativa:          # página que falhou: placeholder
                page = out.new_page(width=p.largura_pt or 595, height=p.altura_pt or 842)
                page.insert_text((72, 100), f"Pagina {p.numero + 1} nao pode ser processada", fontsize=14)
                continue
            if p.nativa and original.is_pdf:
                out.insert_pdf(original, from_page=p.numero, to_page=p.numero)   # mantém o texto original
                page = out[-1]
            else:
                page = out.new_page(width=p.largura_pt, height=p.altura_pt)
                page.insert_image(page.rect, stream=storage.get_bytes(p.imagem_key))
                _texto_invisivel(page, palavras)

            if anonimizar:
                for i in indices_sensiveis(palavras):
                    w = palavras[i]
                    page.add_redact_annot(pymupdf.Rect(w["x0"], w["y0"], w["x1"], w["y1"]) + (-2, -2, 2, 2),
                                          fill=(0, 0, 0))
                # PDF_REDACT_IMAGE_PIXELS: pinta os pixels da imagem por baixo (não é só uma tarja por cima)
                page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS)

        out.set_metadata({"producer": "Document Factory", "title": "documento"})
        return out.tobytes(garbage=4, deflate=True)
    finally:
        out.close()
        original.close()
