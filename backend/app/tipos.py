"""Taxonomia documental — os "5 tipos de referência".

>>> TROQUEM pelos tipos reais assim que a organização liberar os dados de teste. <<<

- palavras: termos que indicam o tipo em qualquer lugar da página (peso 1)
- titulos:  regex que, no TOPO da página, indicam o tipo E o início de documento (peso 3)
Tudo escrito sem acento e minúsculo (o texto é normalizado antes da comparação).
"""

DESCONHECIDO = "DESCONHECIDO"

TIPOS: dict[str, dict] = {
    "IDENTIDADE": {
        "nome": "Documento de identidade (RG/CNH)",
        "palavras": ["registro geral", "carteira de identidade", "secretaria de seguranca",
                     "filiacao", "naturalidade", "data de nascimento", "habilitacao", "orgao expedidor"],
        "titulos": [r"carteira\s+de\s+identidade", r"registro\s+geral", r"carteira\s+nacional\s+de\s+habilitacao"],
    },
    "COMPROVANTE_RESIDENCIA": {
        "nome": "Comprovante de residência",
        "palavras": ["conta de energia", "fatura", "consumo", "kwh", "vencimento", "leitura",
                     "unidade consumidora", "saneamento", "endereco de entrega", "referencia"],
        "titulos": [r"conta\s+de\s+(energia|agua|luz)", r"fatura\s+(de|mensal)", r"segunda\s+via"],
    },
    "CONTRATO": {
        "nome": "Contrato",
        "palavras": ["contratante", "contratada", "clausula", "objeto", "vigencia", "foro",
                     "rescisao", "partes", "testemunhas", "assinatura"],
        "titulos": [r"contrato\s+de", r"instrumento\s+particular", r"termo\s+aditivo"],
    },
    "NOTA_FISCAL": {
        "nome": "Nota fiscal",
        "palavras": ["nota fiscal", "danfe", "nf-e", "chave de acesso", "icms", "valor total",
                     "emitente", "destinatario", "natureza da operacao", "cfop"],
        "titulos": [r"danfe", r"nota\s+fiscal(\s+eletronica)?", r"documento\s+auxiliar"],
    },
    "CERTIDAO": {
        "nome": "Certidão",
        "palavras": ["certidao", "certifico", "cartorio", "registro civil", "nascimento",
                     "casamento", "obito", "oficial", "livro", "folha", "termo"],
        "titulos": [r"certidao\s+de", r"republica\s+federativa.*registro\s+civil"],
    },
}


def nome_tipo(codigo: str | None) -> str:
    if not codigo or codigo not in TIPOS:
        return "Desconhecido"
    return TIPOS[codigo]["nome"]
