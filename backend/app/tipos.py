"""Taxonomia documental: tipos de referência + documentos de gestão de terceiros (trabalhistas e da empresa).

>>> Confirmem os tipos, as validades e a lista de exigidos com o mentor e com os dados de teste. <<<

Cada tipo:
- nome:       como aparece na tela
- descricao:  explicação em linguagem natural (vai para o modelo: é a maior alavanca de precisão)
- palavras:   termos que indicam o tipo em qualquer lugar da página (peso 1)
- titulos:    regex que, no TOPO da página, indicam o tipo E o início de documento (peso 3)
- prioridade: prioridade base na fila de revisão (alta | media | baixa)
- campos:     o que o resumo deve extrair
- validade:   regra usada quando o documento NÃO traz a data de validade escrita
              None = não vence · {"meses": N} ou {"dias": N} a partir da data de emissão/exame
              {"por_nr": {...}, "meses": N} = certificado de NR (reciclagem depende da norma)
Tudo escrito sem acento e minúsculo (o texto é normalizado antes da comparação).
"""

DESCONHECIDO = "DESCONHECIDO"

TIPOS: dict[str, dict] = {
    # ------------------------------------------------------------ documentos pessoais / gerais
    "IDENTIDADE": {
        "nome": "Documento de identidade (RG/CNH)",
        "descricao": "RG ou CNH: documento oficial com foto, nome, filiação, número de registro e órgão expedidor. "
                     "A CNH traz data de validade impressa.",
        "palavras": ["registro geral", "carteira de identidade", "secretaria de seguranca",
                     "filiacao", "naturalidade", "data de nascimento", "habilitacao", "orgao expedidor"],
        "titulos": [r"carteira\s+de\s+identidade", r"registro\s+geral", r"carteira\s+nacional\s+de\s+habilitacao"],
        "prioridade": "media",
        "campos": ["tipo_documento", "orgao_expedidor", "data_expedicao", "naturalidade"],
        "validade": None,
    },
    "COMPROVANTE_RESIDENCIA": {
        "nome": "Comprovante de residência",
        "descricao": "Conta de consumo (energia, água, telefone) com endereço do cliente, mês de referência e valor.",
        "palavras": ["conta de energia", "fatura", "consumo", "kwh", "leitura",
                     "unidade consumidora", "saneamento", "endereco de entrega", "referencia"],
        "titulos": [r"conta\s+de\s+(energia|agua|luz)", r"fatura\s+(de|mensal)", r"segunda\s+via"],
        "prioridade": "baixa",
        "campos": ["empresa", "mes_referencia", "vencimento", "valor", "cidade"],
        "validade": None,
    },
    "CONTRATO": {
        "nome": "Contrato",
        "descricao": "Contrato entre partes (prestação de serviços, locação, trabalho): cláusulas, objeto, valor, "
                     "vigência e foro. Pode ter várias páginas.",
        "palavras": ["contratante", "contratada", "clausula", "objeto", "vigencia", "foro",
                     "rescisao", "partes", "testemunhas", "assinatura"],
        "titulos": [r"contrato\s+de", r"instrumento\s+particular", r"termo\s+aditivo"],
        "prioridade": "alta",
        "campos": ["partes", "objeto", "valor", "vigencia", "foro"],
        "validade": None,   # a vigência vem do texto (cláusula de vigência), não de regra fixa
    },
    "NOTA_FISCAL": {
        "nome": "Nota fiscal",
        "descricao": "Nota fiscal eletrônica / DANFE: emitente, destinatário, chave de acesso, impostos e valor total.",
        "palavras": ["nota fiscal", "danfe", "nf-e", "chave de acesso", "icms", "valor total",
                     "emitente", "destinatario", "natureza da operacao", "cfop"],
        "titulos": [r"danfe", r"nota\s+fiscal(\s+eletronica)?", r"documento\s+auxiliar"],
        "prioridade": "media",
        "campos": ["emitente", "destinatario", "numero", "data_emissao", "valor_total"],
        "validade": None,
    },
    "CERTIDAO": {
        "nome": "Certidão de registro civil",
        "descricao": "Certidão de nascimento, casamento ou óbito emitida por cartório de registro civil.",
        "palavras": ["certifico", "cartorio", "registro civil", "nascimento",
                     "casamento", "obito", "oficial", "livro", "folha", "termo"],
        "titulos": [r"certidao\s+de\s+(nascimento|casamento|obito|inteiro\s+teor)",
                    r"registro\s+civil\s+das\s+pessoas\s+naturais"],
        "prioridade": "media",
        "campos": ["tipo_certidao", "cartorio", "data_registro", "livro_folha"],
        "validade": None,
    },
    # ------------------------------------------------------------ documentos do trabalhador terceirizado
    "ASO": {
        "nome": "Atestado de Saúde Ocupacional (ASO)",
        "descricao": "Atestado emitido por médico do trabalho após exame admissional, periódico, de retorno, "
                     "de mudança de função ou demissional; diz se o trabalhador está apto ou inapto à função.",
        "palavras": ["atestado de saude ocupacional", "apto", "inapto", "exame admissional", "exame periodico",
                     "medico do trabalho", "medico examinador", "pcmso", "riscos ocupacionais", "crm"],
        "titulos": [r"atestado\s+de\s+saude\s+ocupacional", r"\baso\b"],
        "prioridade": "alta",
        "campos": ["tipo_exame", "resultado", "data_exame", "funcao", "riscos"],
        "validade": {"meses": 12},
    },
    "FICHA_EPI": {
        "nome": "Ficha de entrega de EPI",
        "descricao": "Ficha de controle de entrega de Equipamento de Proteção Individual (NR-6): lista de EPIs, "
                     "número do CA, data de entrega e assinatura do trabalhador.",
        "palavras": ["equipamento de protecao individual", "epi", "certificado de aprovacao", "entrega",
                     "devolucao", "nr-6", "nr 6", "luva", "capacete", "botina", "oculos de protecao"],
        "titulos": [r"ficha\s+de\s+(entrega|controle)\s+de\s+(epi|equipamentos?)",
                    r"equipamentos?\s+de\s+protecao\s+individual"],
        "prioridade": "media",
        "campos": ["itens", "data_entrega", "funcao"],
        "validade": None,
    },
    "CERTIFICADO_NR": {
        "nome": "Certificado de treinamento (NR)",
        "descricao": "Certificado de conclusão de treinamento obrigatório de Norma Regulamentadora (NR-10 elétrica, "
                     "NR-33 espaço confinado, NR-35 trabalho em altura...), com carga horária e data de conclusão.",
        "palavras": ["certificado", "treinamento", "carga horaria", "norma regulamentadora", "instrutor",
                     "conteudo programatico", "reciclagem", "nr-10", "nr-35", "nr-33", "concluiu"],
        "titulos": [r"certificado\s+de\s+(treinamento|capacitacao|conclusao|qualificacao)"],
        "prioridade": "alta",
        "campos": ["norma", "carga_horaria", "data_conclusao", "instituicao"],
        # reciclagem: NR-10 e NR-35 a cada 2 anos, NR-33 a cada ano (confirmar com o mentor)
        "validade": {"meses": 24, "por_nr": {"10": 24, "33": 12, "35": 24, "12": 24, "20": 12}},
    },
    "CONTRACHEQUE": {
        "nome": "Contracheque (holerite)",
        "descricao": "Recibo de pagamento de salário de uma competência (mês): proventos, descontos (INSS, IRRF), "
                     "líquido a receber e base de FGTS.",
        "palavras": ["contracheque", "holerite", "recibo de pagamento", "salario base", "proventos", "descontos",
                     "liquido a receber", "irrf", "base fgts", "competencia"],
        "titulos": [r"contracheque", r"holerite", r"recibo\s+de\s+pagamento\s+de\s+salario",
                    r"demonstrativo\s+de\s+pagamento"],
        "prioridade": "baixa",
        "campos": ["competencia", "salario_base", "liquido", "empresa"],
        "validade": None,
    },
    "GUIA_FGTS": {
        "nome": "Guia de recolhimento do FGTS",
        "descricao": "Guia de pagamento do FGTS de uma competência (FGTS Digital / GFIP), com valor e código de barras. "
                     "O vencimento é prazo de pagamento, não validade do documento.",
        "palavras": ["guia do fgts", "fgts digital", "gfip", "recolhimento", "competencia", "codigo de barras",
                     "valor a recolher", "empregador"],
        "titulos": [r"guia\s+(de\s+recolhimento\s+)?do\s+fgts", r"fgts\s+digital", r"\bgfip\b"],
        "prioridade": "media",
        "campos": ["competencia", "valor", "vencimento_pagamento", "empregador"],
        "validade": None,
    },
    "CTPS": {
        "nome": "CTPS / ficha de registro do empregado",
        "descricao": "Carteira de Trabalho ou ficha de registro: dados do contrato de trabalho, cargo, CBO, "
                     "data de admissão e remuneração.",
        "palavras": ["carteira de trabalho", "ctps", "registro de empregado", "ficha de registro", "admissao",
                     "cargo", "cbo", "pis", "remuneracao", "empregador"],
        "titulos": [r"carteira\s+de\s+trabalho", r"ficha\s+de\s+registro(\s+de\s+empregado)?",
                    r"registro\s+de\s+empregado"],
        "prioridade": "media",
        "campos": ["cargo", "cbo", "data_admissao", "empregador"],
        "validade": None,
    },
    # ------------------------------------------------------------ regularidade da empresa prestadora
    "CND_FEDERAL": {
        "nome": "Certidão negativa de débitos federais",
        "descricao": "Certidão da Receita Federal/PGFN sobre tributos federais e dívida ativa da União; "
                     "traz a data de validade (em geral 180 dias).",
        "palavras": ["certidao negativa", "receita federal", "divida ativa da uniao", "pgfn", "tributos federais",
                     "procuradoria-geral da fazenda nacional", "valida ate"],
        "titulos": [r"certidao\s+(negativa|positiva\s+com\s+efeitos\s+de\s+negativa)\s+de\s+debitos\s+relativos",
                    r"tributos\s+federais"],
        "prioridade": "alta",
        "campos": ["empresa", "situacao", "data_emissao", "validade"],
        "validade": {"dias": 180},
    },
    "CRF_FGTS": {
        "nome": "Certificado de Regularidade do FGTS (CRF)",
        "descricao": "Certificado da Caixa que comprova a regularidade da empresa com o FGTS; validade curta (30 dias).",
        "palavras": ["certificado de regularidade", "crf", "fgts", "caixa economica federal", "situacao regular",
                     "validade"],
        "titulos": [r"certificado\s+de\s+regularidade\s+do\s+fgts"],
        "prioridade": "alta",
        "campos": ["empresa", "situacao", "validade"],
        "validade": {"dias": 30},
    },
    "CNDT": {
        "nome": "Certidão negativa de débitos trabalhistas (CNDT)",
        "descricao": "Certidão da Justiça do Trabalho (Banco Nacional de Devedores Trabalhistas); validade de 180 dias.",
        "palavras": ["debitos trabalhistas", "cndt", "justica do trabalho", "banco nacional de devedores trabalhistas",
                     "tribunal superior do trabalho"],
        "titulos": [r"certidao\s+negativa\s+de\s+debitos\s+trabalhistas"],
        "prioridade": "alta",
        "campos": ["empresa", "situacao", "data_emissao", "validade"],
        "validade": {"dias": 180},
    },
}

# documentos que todo trabalhador terceirizado precisa ter (checklist do dossiê) — configurável
DOCUMENTOS_EXIGIDOS_TRABALHADOR = ["IDENTIDADE", "CTPS", "ASO", "FICHA_EPI"]

# prioridade: guardada como número no banco (ordena fácil), exibida como texto na API
PRIORIDADES = {"baixa": 1, "media": 2, "alta": 3}
PRIORIDADE_NOME = {v: k for k, v in PRIORIDADES.items()}
PRIORIDADE_DESCONHECIDO = "alta"   # tipo não identificado precisa de atenção logo


def nome_tipo(codigo: str | None) -> str:
    if not codigo or codigo not in TIPOS:
        return "Desconhecido"
    return TIPOS[codigo]["nome"]


def prioridade_do_tipo(codigo: str | None) -> int:
    if not codigo or codigo not in TIPOS:
        return PRIORIDADES[PRIORIDADE_DESCONHECIDO]
    return PRIORIDADES[TIPOS[codigo].get("prioridade", "media")]


def campos_do_tipo(codigo: str | None) -> list[str]:
    if not codigo or codigo not in TIPOS:
        return []
    return list(TIPOS[codigo].get("campos", []))


def regra_validade(codigo: str | None) -> dict | None:
    if not codigo or codigo not in TIPOS:
        return None
    return TIPOS[codigo].get("validade")
