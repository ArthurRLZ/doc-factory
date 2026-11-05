"""Anonimização (LGPD): mascara dados pessoais no texto, na imagem e no PDF.

Fluxo de privacidade:
  OCR → detecta CPF/CNPJ/RG/e-mail/telefone → texto mascarado vai pro banco e pro modelo
                                           → imagem enviada ao modelo vai com tarja
                                           → PDF anonimizado usa redaction real do PyMuPDF
Evolução: Microsoft Presidio + spaCy pt para NOMES e endereços.
"""
import io
import re

from PIL import Image, ImageDraw

# ordem importa: CNPJ antes de CPF (CNPJ contém um padrão parecido)
PADROES: dict[str, re.Pattern] = {
    "CNPJ": re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"),
    "CPF": re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\b\d{11}\b"),
    "RG": re.compile(r"\b\d{1,2}\.\d{3}\.\d{3}-?[\dXx]\b"),
    "EMAIL": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "TELEFONE": re.compile(r"\(?\b\d{2}\)?\s?9?\d{4}-\d{4}\b"),
}


def mascarar_texto(texto: str) -> tuple[str, dict[str, int]]:
    contagem = {}
    for nome, rx in PADROES.items():
        texto, n = rx.subn(f"[{nome}]", texto)
        if n:
            contagem[nome] = n
    return texto, contagem


def indices_sensiveis(palavras: list[dict]) -> set[int]:
    """Quais palavras (por índice) fazem parte de um dado sensível.
    Junta as palavras com espaço, roda os regex e mapeia de volta pelas posições."""
    if not palavras:
        return set()
    offsets, partes, pos = [], [], 0
    for w in palavras:
        offsets.append((pos, pos + len(w["t"])))
        partes.append(w["t"])
        pos += len(w["t"]) + 1
    texto = " ".join(partes)
    alvo = set()
    for rx in PADROES.values():
        for m in rx.finditer(texto):
            for i, (a, b) in enumerate(offsets):
                if a < m.end() and b > m.start():
                    alvo.add(i)
    return alvo


def tarjar_imagem(png: bytes, palavras: list[dict], indices: set[int], dpi: int, margem_px: int = 4) -> bytes:
    """Pinta caixas pretas sobre os dados sensíveis (usado antes de mandar a imagem para o modelo)."""
    if not indices:
        return png
    img = Image.open(io.BytesIO(png)).convert("L")
    draw = ImageDraw.Draw(img)
    k = dpi / 72.0
    for i in indices:
        w = palavras[i]
        draw.rectangle([w["x0"] * k - margem_px, w["y0"] * k - margem_px,
                        w["x1"] * k + margem_px, w["y1"] * k + margem_px], fill=0)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()
