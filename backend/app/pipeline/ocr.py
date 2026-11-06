"""Etapa 2 — OCR com Tesseract (idioma 'por').

Usamos image_to_data porque ele devolve, para CADA palavra:
texto + caixa (bbox) + confiança. A caixa serve para:
  - montar o PDF pesquisável (texto invisível na posição certa)
  - tarjar CPF/RG na imagem e no PDF (anonimização)
  - saber o que está no TOPO da página (título → início de documento)
"""
import io
from dataclasses import dataclass

import pytesseract
from PIL import Image, ImageOps

from app.config import settings

LIMIAR_TINTA_VAZIA = 0.0005   # < 0,05% de pixels escuros = vazia, pula o OCR


@dataclass
class ResultadoOCR:
    texto: str
    palavras: list[dict]       # {x0,y0,x1,y1 (em pontos PDF), t, c (0-100), b (bloco), l (linha)}
    confianca: float           # média ponderada pelo tamanho da palavra
    tinta: float               # fração de pixels escuros (detecta página em branco)
    conteudo_incerto: bool = False


def preprocessar(img: Image.Image) -> Image.Image:
    """Pré-processamento leve. Ideias p/ evoluir: deskew (tesseract --psm 0), binarização Sauvola, remoção de bordas."""
    img = img.convert("L")
    return ImageOps.autocontrast(img, cutoff=1)


def densidade_tinta(img: Image.Image) -> float:
    hist = img.histogram()
    escuros = sum(hist[:128])
    return escuros / max(1, img.width * img.height)


def ocr_png(png: bytes, dpi: int | None = None) -> ResultadoOCR:
    dpi = dpi or settings.DPI_OCR
    bruta = Image.open(io.BytesIO(png)).convert("L")
    tinta = densidade_tinta(bruta)          # ANTES do autocontraste (que escurece páginas vazias)
    # Traços cinza-claro também são conteúdo potencial, mesmo sem pixels abaixo de 128.
    if tinta == 0 and bruta.getextrema()[0] < 245:
        tinta = 1 / (bruta.width * bruta.height)
    if tinta == 0:
        # Apenas branco uniforme é inequívoco; texto pequeno pode ocupar área mínima.
        return ResultadoOCR(texto="", palavras=[], confianca=0.0, tinta=tinta)
    desloc_x = desloc_y = 0
    if tinta < LIMIAR_TINTA_VAZIA:
        # Conteúdo esparso numa imagem grande: recortar a área escura impede que
        # o Tesseract ignore texto pequeno cercado por uma grande margem branca.
        caixa = bruta.point(lambda pixel: 255 if pixel < 128 else 0).getbbox()
        if not caixa:
            caixa = bruta.point(lambda pixel: 255 if pixel < 245 else 0).getbbox()
        if caixa:
            margem = 24
            x0, y0, x1, y1 = caixa
            # Poeira distribuída pela página inteira não forma uma região útil:
            # evita que o Tesseract transforme ruído de scanner em palavras fictícias.
            if (x1 - x0) * (y1 - y0) > bruta.width * bruta.height * 0.5:
                return ResultadoOCR(texto="", palavras=[], confianca=0.0, tinta=0.0, conteudo_incerto=True)
            desloc_x, desloc_y = max(0, x0 - margem), max(0, y0 - margem)
            bruta = bruta.crop((desloc_x, desloc_y, min(bruta.width, x1 + margem), min(bruta.height, y1 + margem)))
    img = preprocessar(bruta)

    try:
        d = pytesseract.image_to_data(
            img, lang=settings.OCR_LANG, config=f"--psm {6 if tinta < LIMIAR_TINTA_VAZIA else settings.OCR_PSM}",
            output_type=pytesseract.Output.DICT, timeout=settings.OCR_TIMEOUT_S,
        )
    except RuntimeError as e:  # pytesseract levanta RuntimeError no timeout
        raise TimeoutError(f"Tesseract excedeu {settings.OCR_TIMEOUT_S}s") from e

    escala = 72.0 / dpi   # pixel → ponto PDF
    palavras, linhas = [], {}
    soma_conf, soma_peso = 0.0, 0
    for i, t in enumerate(d["text"]):
        t = (t or "").strip()
        conf = float(d["conf"][i])
        if not t or conf < 0:
            continue
        x, y, w, h = d["left"][i] + desloc_x, d["top"][i] + desloc_y, d["width"][i], d["height"][i]
        bloco, linha = d["block_num"][i], (d["block_num"][i], d["par_num"][i], d["line_num"][i])
        palavras.append({"x0": x * escala, "y0": y * escala, "x1": (x + w) * escala, "y1": (y + h) * escala,
                         "t": t, "c": conf, "b": bloco, "l": d["line_num"][i]})
        linhas.setdefault(linha, []).append(t)
        soma_conf += conf * len(t)
        soma_peso += len(t)

    # reconstrói o texto preservando linhas e blocos
    partes, bloco_ant = [], None
    for (b, _p, _l), ws in linhas.items():
        if bloco_ant is not None and b != bloco_ant:
            partes.append("")
        partes.append(" ".join(ws))
        bloco_ant = b

    return ResultadoOCR(texto="\n".join(partes), palavras=palavras,
                        confianca=(soma_conf / soma_peso) if soma_peso else 0.0, tinta=tinta)


def e_pagina_em_branco(n_palavras: int, tinta: float) -> bool:
    # poucas palavras E quase nenhuma tinta (tolera sujeira de scanner).
    # Calibrem com os dados reais: no lote sintético, páginas com texto ficam entre 0,6% e 1,6% de tinta.
    # Uma única palavra reconhecida não deve ser descartada como separador.
    # Qualquer conteúdo escuro sem texto é ambíguo e precisa de revisão.
    return n_palavras == 0 and tinta == 0
