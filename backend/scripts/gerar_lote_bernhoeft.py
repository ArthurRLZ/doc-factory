"""Gera um lote FALSO "escaneado" de gestão de terceiros (documentos trabalhistas + regularidade da empresa).

    python scripts/gerar_lote_bernhoeft.py lote_terceiros.pdf

As datas são RELATIVAS A HOJE, para a demo continuar coerente em qualquer dia:
  - documentos vencidos, vencendo em menos de 30 dias e vigentes
  - 2 trabalhadores com CPFs diferentes; o trabalhador B está SEM ficha de EPI (checklist acusa)
Conteúdo (14 páginas → 12 documentos esperados):
   1     ASO trabalhador A (exame há 13 meses → vencido pela regra de 12 meses)
   2     Ficha de EPI trabalhador A
   3     Certificado NR-35 trabalhador A (concluído há 10 meses → vigente)
   4     Contracheque trabalhador A
   5     CTPS / ficha de registro trabalhador B
   6     ASO trabalhador B (exame há 2 meses → vigente)
   7     Certificado NR-10 trabalhador B (concluído há ~23 meses e meio → vencendo)
   8     página em branco (separador)
   9     CND federal ("Válida até" daqui a 70 dias → vigente)
  10     CRF do FGTS ("Validade" terminou há 5 dias → vencido)
  11     CNDT ("Validade" daqui a 20 dias → vencendo)
  12-13  Contrato de prestação de serviços ("vigência de 12 meses a partir de ...", termina em ~25 dias)
  14     Guia do FGTS
Todos os nomes e números são inventados (CPFs com dígito verificador válido, mas fictícios).
"""
import os
import sys
from datetime import date, timedelta

import pymupdf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_lote_teste import pagina  # noqa: E402  (mesmo visual "escaneado")

HOJE = date.today()


def d(dias: int) -> str:
    return (HOJE + timedelta(days=dias)).strftime("%d/%m/%Y")


def meses_atras(m: int, dias_extra: int = 0) -> str:
    return (HOJE - timedelta(days=round(m * 30.44) + dias_extra)).strftime("%d/%m/%Y")


EMPRESA = "Serviços Gerais Fictícia LTDA, CNPJ 11.222.333/0001-81"
A = ("Carlos Fictício Pereira", "529.982.247-25")
B = ("Fernanda Fictícia Lima", "168.995.350-09")
inicio_contrato = HOJE - timedelta(days=365 - 25)          # 12 meses que terminam daqui a ~25 dias
competencia = (HOJE.replace(day=1) - timedelta(days=1)).strftime("%m/%Y")

PAGINAS = [
    ("ATESTADO DE SAÚDE OCUPACIONAL - ASO", [
        f"Empresa: {EMPRESA}",
        f"Nome: {A[0]}   CPF {A[1]}",
        "Função: Eletricista de manutenção",
        "Exame: PERIÓDICO",
        "Riscos ocupacionais: eletricidade, ruído",
        f"Data do exame: {meses_atras(13)}",
        "Resultado: APTO para a função",
        "Médico examinador: Dr. Paulo Fictício - CRM-PE 12345",
    ], None),
    ("FICHA DE ENTREGA DE EPI", [
        "Equipamentos de Proteção Individual - NR-6",
        f"Empregado: {A[0]}   CPF {A[1]}",
        "Item: Capacete de segurança   CA 31469",
        "Item: Luva isolante classe 0   CA 28011",
        "Item: Botina de segurança   CA 40377",
        f"Data de entrega: {meses_atras(13)}",
        "Declaro ter recebido os EPIs acima. Assinatura: ________",
    ], None),
    ("CERTIFICADO DE TREINAMENTO", [
        f"Certificamos que {A[0]}, CPF {A[1]},",
        "concluiu o treinamento de NR-35 - Trabalho em Altura,",
        "com carga horária de 8 horas.",
        f"Data de conclusão: {meses_atras(10)}",
        "Instrutor: Roberto Fictício - Técnico de Segurança",
        "Conteúdo programático conforme a Norma Regulamentadora 35.",
    ], None),
    ("RECIBO DE PAGAMENTO DE SALÁRIO", [
        f"Empregador: {EMPRESA}",
        f"Empregado: {A[0]}   CPF {A[1]}",
        f"Competência: {competencia}",
        "Salário base: R$ 2.800,00   Proventos: R$ 3.150,00",
        "Descontos: INSS R$ 283,50   IRRF R$ 0,00",
        "Líquido a receber: R$ 2.866,50   Base FGTS: R$ 3.150,00",
    ], None),
    ("FICHA DE REGISTRO DE EMPREGADO", [
        f"Empregador: {EMPRESA}",
        f"Nome: {B[0]}   CPF {B[1]}",
        "Cargo: Técnica de manutenção elétrica   CBO 3131-10",
        f"Data de admissão: {meses_atras(30)}",
        "Remuneração: R$ 3.400,00   PIS 120.45678.90-1",
        "Carteira de Trabalho Digital - CTPS",
    ], None),
    ("ATESTADO DE SAÚDE OCUPACIONAL - ASO", [
        f"Empresa: {EMPRESA}",
        f"Nome: {B[0]}   CPF {B[1]}",
        "Função: Técnica de manutenção elétrica",
        "Exame: PERIÓDICO",
        f"Data do exame: {meses_atras(2)}",
        "Resultado: APTO para a função",
        "Médico examinador: Dra. Lúcia Fictícia - CRM-PE 67890",
    ], None),
    ("CERTIFICADO DE TREINAMENTO", [
        f"Certificamos que {B[0]}, CPF {B[1]},",
        "concluiu o treinamento de NR-10 - Segurança em Instalações",
        "e Serviços em Eletricidade, com carga horária de 40 horas.",
        f"Data de conclusão: {meses_atras(24, dias_extra=-15)}",
        "Instrutor: Roberto Fictício - Engenheiro Eletricista",
        "Conteúdo programático conforme a Norma Regulamentadora 10.",
    ], None),
    ("", [], None),  # em branco: separa documentos do trabalhador dos da empresa
    ("CERTIDÃO NEGATIVA DE DÉBITOS RELATIVOS AOS TRIBUTOS FEDERAIS", [
        "E À DÍVIDA ATIVA DA UNIÃO",
        f"Contribuinte: {EMPRESA}",
        "Ressalvado o direito da Fazenda Nacional, certifica-se que não",
        "constam pendências em nome do contribuinte acima identificado.",
        "Receita Federal do Brasil - Procuradoria-Geral da Fazenda Nacional",
        f"Emitida em {d(-110)}. Válida até {d(70)}.",
    ], None),
    ("CERTIFICADO DE REGULARIDADE DO FGTS - CRF", [
        f"Empregador: {EMPRESA}",
        "A Caixa Econômica Federal certifica que o empregador acima",
        "encontra-se em situação regular perante o FGTS.",
        f"Validade: {d(-35)} a {d(-5)}",
        "Certificação número: 2026110512345678",
    ], None),
    ("CERTIDÃO NEGATIVA DE DÉBITOS TRABALHISTAS", [
        f"Nome: {EMPRESA}",
        "Certifica-se que a pessoa jurídica acima NÃO CONSTA do Banco",
        "Nacional de Devedores Trabalhistas - Justiça do Trabalho.",
        f"Expedição: {d(-160)}",
        f"Validade: {d(20)} (180 dias contados da expedição).",
    ], None),
    ("CONTRATO DE PRESTAÇÃO DE SERVIÇOS", [
        "CONTRATANTE: Indústria Contratante Fictícia S.A., CNPJ 44.555.666/0001-77.",
        f"CONTRATADA: {EMPRESA}.",
        "CLÁUSULA PRIMEIRA - DO OBJETO: manutenção elétrica predial.",
        "CLÁUSULA SEGUNDA - DA VIGÊNCIA: o presente contrato terá",
        f"vigência de 12 (doze) meses a partir de {inicio_contrato.strftime('%d/%m/%Y')}.",
        "CLÁUSULA TERCEIRA - DO VALOR: R$ 18.000,00 mensais.",
    ], "Página 1 de 2"),
    (None, [
        "CLÁUSULA QUARTA - DAS OBRIGAÇÕES: a CONTRATADA manterá em dia",
        "os ASOs, treinamentos de NR e a documentação de seus empregados.",
        "CLÁUSULA QUINTA - DO FORO: comarca de Garanhuns/PE.",
        "Assinatura das partes e testemunhas.",
    ], "Página 2 de 2"),
    ("GUIA DO FGTS - FGTS DIGITAL", [
        f"Empregador: {EMPRESA}",
        f"Competência: {competencia}",
        "Valor a recolher: R$ 1.904,00",
        f"Pagar até: {d(15)}",
        "Código de barras: 85800000019 04000000000 12345678901 23456789012",
    ], None),
]


def main(saida: str):
    doc = pymupdf.open()
    for i, (t, ls, r) in enumerate(PAGINAS):
        page = doc.new_page(width=595, height=842)
        page.insert_image(page.rect, stream=pagina(t, ls, r, 100 + i))
    doc.save(saida, garbage=4, deflate=True)
    print(f"{saida}: {doc.page_count} páginas (datas relativas a {HOJE:%d/%m/%Y})")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "lote_terceiros.pdf")
