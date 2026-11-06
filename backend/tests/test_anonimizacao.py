"""Anonimização de nomes, endereços e CEP — no texto, na busca, no resumo e no PDF."""
import json

import pymupdf

from app.pipeline import anonimizar
from app.pipeline.anonimizar import indices_sensiveis, mascarar_texto

AMOSTRA = """CONTRATANTE: Maria Exemplo da Silva, CPF 123.456.789-09, residente em Garanhuns.
CONTRATADA: Empresa Fictícia LTDA, CNPJ 12.345.678/0001-95.
NOME: JOÃO FICTÍCIO DOS SANTOS
FILIAÇÃO: JOSÉ FICTÍCIO / ANA FICTÍCIA
Cliente: Maria Exemplo da Silva
Endereço de entrega: Rua das Flores, 100 - Garanhuns/PE  CEP 55290-000
foi registrado o nascimento de PEDRO FICTÍCIO,
nascido em 02/02/2020, filho de João Fictício e Ana Fictícia.
Av. Santo Antônio, 500, Garanhuns/PE.
Cartório do 1º Ofício de Garanhuns/PE
Distribuidora Fictícia de Energia S.A."""

NOMES = ["Maria Exemplo", "JOÃO FICTÍCIO", "JOSÉ FICTÍCIO", "ANA FICTÍCIA", "PEDRO FICTÍCIO",
         "João Fictício", "Ana Fictícia"]


def test_nomes_enderecos_e_cep_mascarados():
    m, contagem = mascarar_texto(AMOSTRA)
    for nome in NOMES:
        assert nome not in m, nome
    assert "Rua das Flores" not in m and "Santo Antônio" not in m and "55290-000" not in m
    assert contagem["NOME"] >= 6 and contagem["ENDERECO"] == 2 and contagem["CEP"] == 1


def test_empresas_cidades_e_estrutura_preservadas():
    m, _ = mascarar_texto(AMOSTRA)
    for visivel in ("Empresa Fictícia LTDA", "Distribuidora Fictícia de Energia S.A.", "Garanhuns",
                    "Cartório do 1º Ofício", "CONTRATANTE:", "02/02/2020"):
        assert visivel in m, visivel
    assert m.count("\n") == AMOSTRA.count("\n")          # nenhuma quebra de linha engolida


def test_sem_reconhecedor_as_regras_por_rotulo_continuam(monkeypatch):
    monkeypatch.setattr(anonimizar, "_nlp", lambda: None)
    m, _ = mascarar_texto("Cliente: Maria Exemplo da Silva\nNOME: JOÃO FICTÍCIO DOS SANTOS")
    assert "Maria" not in m and "JOÃO" not in m


def test_desligar_nomes_por_configuracao(monkeypatch):
    monkeypatch.setattr(anonimizar.settings, "ANONIMIZAR_NOMES", False)
    m, _ = mascarar_texto("Cliente: Maria Exemplo da Silva, CPF 123.456.789-09")
    assert "Maria Exemplo da Silva" in m and "123.456.789-09" not in m


def test_indices_para_tarja_respeitam_linhas():
    palavras = ([{"t": t, "b": 1, "l": 1} for t in "Cliente: Maria Exemplo da Silva".split()]
                + [{"t": t, "b": 1, "l": 2} for t in "Endereço de entrega: Rua das Flores, 100".split()])
    alvo = {palavras[i]["t"] for i in indices_sensiveis(palavras)}
    assert {"Maria", "Exemplo", "Silva", "Rua", "Flores,", "100"} <= alvo
    assert "Cliente:" not in alvo and "Endereço" not in alvo


# ------------------------------------------------------------------ ponta a ponta
def test_busca_nao_encontra_nomes(processado):
    c, _ = processado
    assert c.get("/busca", params={"q": "Exemplo da Silva"}).json() == []
    assert c.get("/busca", params={"q": "foro"}).json()                 # o resto continua pesquisável


def test_resumos_nao_trazem_nomes(processado):
    c, lote = processado
    docs = c.get(f"/lotes/{lote['id']}/documentos").json()
    corpo = json.dumps(docs, ensure_ascii=False)
    assert "Maria Exemplo" not in corpo and "FICTÍCIO DOS SANTOS" not in corpo


def test_pdf_anonimizado_tarja_nomes(processado):
    c, lote = processado
    docs = c.get(f"/lotes/{lote['id']}/documentos").json()
    rg = next(d for d in docs if d["tipo"] == "IDENTIDADE")

    def texto(anon):
        pdf = c.get(f"/documentos/{rg['id']}/pdf", params={"anonimizado": anon}).content
        return " ".join(p.get_text() for p in pymupdf.open(stream=pdf, filetype="pdf")).upper()

    assert "SANTOS" in texto(False)                    # original tem o nome
    anon = texto(True)
    assert "SANTOS" not in anon and "FILIA" in anon    # anonimizado: nome some, o rótulo fica
