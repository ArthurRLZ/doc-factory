"""Gera uma FOTO sintética com duas folhas sobre a mesa (F8: vários documentos numa mesma imagem).

    python scripts/gerar_duas_folhas.py ../docs/exemplos/duas_folhas.png [--inclinar 5]

Fundo escuro + duas folhas claras com texto inventado (identidade em cima, conta de energia embaixo).
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_lote_teste import FONTE, FONTE_B  # noqa: E402


def folha(largura: int, altura: int, titulo: str, linhas: list[str]) -> Image.Image:
    img = Image.new("RGB", (largura, altura), (250, 250, 248))
    d = ImageDraw.Draw(img)
    fb, fr = ImageFont.truetype(FONTE_B, max(16, largura // 28)), ImageFont.truetype(FONTE, max(12, largura // 38))
    d.text((largura // 14, altura // 10), titulo, font=fb, fill=(20, 20, 20))
    for i, ln in enumerate(linhas):
        d.text((largura // 14, altura // 10 + (i + 2) * (altura // 11)), ln, font=fr, fill=(30, 30, 30))
    return img


def gerar(largura: int = 1240, altura: int = 1754, inclinar: float = 0.0) -> Image.Image:
    mesa = Image.new("RGB", (largura, altura), (55, 58, 62))
    fl, fa = int(largura * 0.82), int(altura * 0.40)
    a = folha(fl, fa, "CARTEIRA DE IDENTIDADE", ["Nome: Maria Exemplo da Silva", "RG 12.345.678-9 SSP/PE",
                                                "Data de nascimento: 01/01/1990", "Naturalidade: Garanhuns/PE"])
    b = folha(fl, fa, "CONTA DE ENERGIA ELÉTRICA", ["Cliente: Maria Exemplo da Silva", "Rua das Flores, 100",
                                                   "Referência: 10/2026", "Total a pagar: R$ 187,40"])
    if inclinar:
        a = a.rotate(inclinar, expand=True, fillcolor=(55, 58, 62))
        b = b.rotate(inclinar, expand=True, fillcolor=(55, 58, 62))
    mesa.paste(a, ((largura - a.width) // 2, int(altura * 0.05)))
    mesa.paste(b, ((largura - b.width) // 2, int(altura * 0.53)))
    return mesa


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("saida", nargs="?", default="duas_folhas.png")
    ap.add_argument("--inclinar", type=float, default=0.0)
    args = ap.parse_args()
    gerar(inclinar=args.inclinar).save(args.saida, optimize=True)
    print(f"{args.saida}: foto sintética com 2 folhas")
