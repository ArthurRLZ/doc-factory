"""Gera um lote FALSO "escaneado" (PDF só com imagens) para testar o pipeline sem dados reais.

    python scripts/gerar_lote_teste.py lote_teste.pdf

Conteúdo (11 páginas → 6 documentos esperados):
  1-3  Contrato com "Página X de 3"
  4    página em branco (separador)
  5    Carteira de identidade
  6-7  Conta de energia (2 páginas, sem numeração)
  8    DANFE / nota fiscal
  9    Certidão de nascimento
  10-11 Contrato sem numeração (título só na 1ª)
Todos os nomes e números são inventados.
"""
import io
import json
import os
import random
import sys

import pymupdf
from PIL import Image, ImageDraw, ImageFilter, ImageFont


def _primeira_fonte(*caminhos: str) -> str:
    """Primeira fonte que existir (Linux → Windows → Mac)."""
    for c in caminhos:
        if os.path.exists(c):
            return c
    raise FileNotFoundError(f"nenhuma fonte encontrada: {caminhos}")


_WIN = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
FONTE = _primeira_fonte("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                        os.path.join(_WIN, "arial.ttf"),
                        "/System/Library/Fonts/Supplemental/Arial.ttf")
FONTE_B = _primeira_fonte("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                          os.path.join(_WIN, "arialbd.ttf"),
                          "/System/Library/Fonts/Supplemental/Arial Bold.ttf")
W, H = 1240, 1754  # A4 @150 dpi

PAGINAS = [
    ("CONTRATO DE PRESTAÇÃO DE SERVIÇOS", [
        "CONTRATANTE: Maria Exemplo da Silva, CPF 123.456.789-09,",
        "residente na Rua das Flores, 100, Garanhuns/PE.",
        "CONTRATADA: Empresa Fictícia LTDA, CNPJ 12.345.678/0001-95.",
        "CLÁUSULA PRIMEIRA - DO OBJETO",
        "O presente contrato tem por objeto a prestação de serviços",
        "de manutenção de equipamentos de informática.",
    ], "Página 1 de 3"),
    (None, [
        "CLÁUSULA SEGUNDA - DA VIGÊNCIA",
        "A vigência deste contrato será de 12 (doze) meses.",
        "CLÁUSULA TERCEIRA - DO VALOR",
        "O valor mensal será de R$ 1.500,00 pagos até o dia 10.",
        "CLÁUSULA QUARTA - DA RESCISÃO",
        "Qualquer das partes poderá rescindir com aviso de 30 dias.",
    ], "Página 2 de 3"),
    (None, [
        "CLÁUSULA QUINTA - DO FORO",
        "Fica eleito o foro da comarca de Garanhuns/PE.",
        "E por estarem justas, as partes assinam o presente.",
        "Garanhuns, 05 de novembro de 2026.",
        "________________________  ________________________",
        "CONTRATANTE                CONTRATADA",
        "Testemunhas: ____________  ____________",
    ], "Página 3 de 3"),
    ("", [], None),  # em branco
    ("CARTEIRA DE IDENTIDADE", [
        "REPÚBLICA FEDERATIVA DO BRASIL",
        "SECRETARIA DE SEGURANÇA PÚBLICA - PE",
        "REGISTRO GERAL: 12.345.678-9",
        "NOME: JOÃO FICTÍCIO DOS SANTOS",
        "FILIAÇÃO: JOSÉ FICTÍCIO / ANA FICTÍCIA",
        "NATURALIDADE: GARANHUNS-PE",
        "DATA DE NASCIMENTO: 01/01/1990",
        "CPF 987.654.321-00   ÓRGÃO EXPEDIDOR: SDS/PE",
    ], None),
    ("CONTA DE ENERGIA ELÉTRICA", [
        "Distribuidora Fictícia de Energia S.A.",
        "Unidade consumidora: 7000123456",
        "Cliente: Maria Exemplo da Silva",
        "Endereço de entrega: Rua das Flores, 100 - Garanhuns/PE",
        "Referência: 10/2026      Vencimento: 15/11/2026",
        "Consumo: 182 kWh         Total a pagar: R$ 154,32",
    ], None),
    (None, [
        "Histórico de consumo (kWh)",
        "05/2026: 170   06/2026: 175   07/2026: 190",
        "08/2026: 168   09/2026: 179   10/2026: 182",
        "Leitura anterior: 10234   Leitura atual: 10416",
        "Atendimento: (87) 99999-1234  contato@fict.example",
    ], None),
    ("DANFE - DOCUMENTO AUXILIAR DA NOTA FISCAL ELETRÔNICA", [
        "NF-e Nº 000.123.456   Série 1",
        "Chave de acesso: 2611 1234 5678 0001 9555 0010 0012 3456 1000 0000 01",
        "Natureza da operação: Venda de mercadoria   CFOP 5102",
        "Emitente: Empresa Fictícia LTDA   CNPJ 12.345.678/0001-95",
        "Destinatário: Maria Exemplo da Silva   CPF 123.456.789-09",
        "Base de cálculo ICMS: R$ 800,00   Valor ICMS: R$ 144,00",
        "Valor total da nota: R$ 800,00",
    ], None),
    ("CERTIDÃO DE NASCIMENTO", [
        "REGISTRO CIVIL DAS PESSOAS NATURAIS",
        "Cartório do 1º Ofício de Garanhuns/PE",
        "Certifico que no livro A-12, folha 34, termo 5678,",
        "foi registrado o nascimento de PEDRO FICTÍCIO,",
        "nascido em 02/02/2020, filho de João Fictício e Ana Fictícia.",
        "O referido é verdade e dou fé. Oficial do registro.",
    ], None),
    ("CONTRATO DE LOCAÇÃO RESIDENCIAL", [
        "LOCADOR e CONTRATANTE: José Fictício, CPF 111.444.777-35.",
        "LOCATÁRIO e CONTRATADA: Ana Fictícia.",
        "CLÁUSULA PRIMEIRA - DO OBJETO: imóvel situado na",
        "Av. Santo Antônio, 500, Garanhuns/PE.",
        "CLÁUSULA SEGUNDA - DA VIGÊNCIA: 30 meses.",
    ], None),
    (None, [
        "CLÁUSULA TERCEIRA - DO ALUGUEL: R$ 1.200,00 mensais.",
        "CLÁUSULA QUARTA - DA RESCISÃO: multa de 3 aluguéis.",
        "CLÁUSULA QUINTA - DO FORO: comarca de Garanhuns/PE.",
        "Assinatura das partes e testemunhas.",
    ], None),
]


def pagina(titulo, linhas, rodape, seed) -> bytes:
    rnd = random.Random(seed)
    img = Image.new("L", (W, H), 250)
    d = ImageDraw.Draw(img)
    fb, fr = ImageFont.truetype(FONTE_B, 34), ImageFont.truetype(FONTE, 26)
    y = 150
    if titulo:
        d.text((110, y), titulo, font=fb, fill=20)
        y += 110
    for ln in linhas:
        d.text((110, y), ln, font=fr, fill=25)
        y += 52
    if rodape:
        d.text((W - 360, H - 140), rodape, font=fr, fill=40)
    # "cara de scanner": leve rotação, ruído e desfoque
    img = img.rotate(rnd.uniform(-0.6, 0.6), fillcolor=250, resample=Image.BICUBIC)
    px = img.load()
    for _ in range(4000):
        px[rnd.randrange(W), rnd.randrange(H)] = rnd.randrange(150, 230)
    img = img.filter(ImageFilter.GaussianBlur(0.4))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# tipo esperado de cada documento, pelo título da 1ª página (a separação sai da própria lista PAGINAS)
TIPO_DO_TITULO = {
    "CONTRATO DE PRESTAÇÃO DE SERVIÇOS": "CONTRATO",
    "CARTEIRA DE IDENTIDADE": "IDENTIDADE",
    "CONTA DE ENERGIA ELÉTRICA": "COMPROVANTE_RESIDENCIA",
    "DANFE - DOCUMENTO AUXILIAR DA NOTA FISCAL ELETRÔNICA": "NOTA_FISCAL",
    "CERTIDÃO DE NASCIMENTO": "CERTIDAO",
    "CONTRATO DE LOCAÇÃO RESIDENCIAL": "CONTRATO",
}


def montar_gabarito(paginas: list, tipo_do_titulo: dict[str, str], nome: str) -> dict:
    """Verdade conhecida do lote (F5), derivada da estrutura: título = início de documento,
    None = continuação, "" = página em branco (separador, não pertence a documento). Páginas 0-based."""
    docs: list[dict] = []
    for i, (titulo, _linhas, _rodape) in enumerate(paginas):
        if titulo == "":
            continue
        if titulo is None:
            docs[-1]["paginas"].append(i)
        else:
            docs.append({"tipo": tipo_do_titulo[titulo], "paginas": [i]})
    return {"lote": nome, "documentos": docs}


def salvar_gabarito(saida_pdf: str, gabarito: dict) -> str:
    caminho = os.path.splitext(saida_pdf)[0] + ".gabarito.json"
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(gabarito, f, ensure_ascii=False, indent=2)
    return caminho


def main(saida: str):
    doc = pymupdf.open()
    for i, (t, ls, r) in enumerate(PAGINAS):
        page = doc.new_page(width=595, height=842)
        page.insert_image(page.rect, stream=pagina(t, ls, r, i))
    doc.save(saida, garbage=4, deflate=True)
    salvar_gabarito(saida, montar_gabarito(PAGINAS, TIPO_DO_TITULO, os.path.basename(saida)))
    print(f"{saida}: {doc.page_count} páginas (+ gabarito)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "lote_teste.pdf")
