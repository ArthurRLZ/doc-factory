"""Relatório de risco de privacidade: contagem de identificadores, pessoas distintas e dados sensíveis."""
import json

import pytest

from app.db import SessionLocal
from app.models import Documento, Lote, Pagina, novo_id
from app.pipeline import privacidade
from app.pipeline.anonimizar import mascarar_texto
from app.status import StatusLote


# ---------------------------------------------------------------- funções puras
def test_marcadores_cobrem_tudo_que_a_anonimizacao_gera():
    """Se a anonimização ganhar um rótulo novo, o relatório precisa conhecê-lo (senão ele sumiria da contagem)."""
    texto = ("Nome: Maria da Silva CPF 529.982.247-25 RG 12.345.678-9 CNPJ 11.222.333/0001-81 "
             "email a@b.com fone (81) 98765-4321 Rua das Flores, 120 CEP 55290-000")
    _, contagem = mascarar_texto(texto)
    desconhecidos = set(contagem) - set(privacidade.PESSOAIS) - set(privacidade.EMPRESA)
    assert not desconhecidos, f"rótulos sem tratamento no relatório: {desconhecidos}"


def test_conta_identificadores_pelos_marcadores():
    a = privacidade.analisar_documento("CONTRATO", "[NOME] e [NOME] — CPF [CPF], [CPF], [CPF]; empresa [CNPJ]")
    assert a.marcadores == {"NOME": 2, "CPF": 3, "CNPJ": 1} and a.tem_pessoais
    assert not privacidade.analisar_documento("CONTRATO", "só [CNPJ] da empresa").tem_pessoais


def test_tipo_aso_ja_e_saude():
    a = privacidade.analisar_documento("ASO", "texto qualquer sem palavra-chave")
    assert list(a.sensiveis) == ["SAUDE"] and a.sensiveis["SAUDE"][0] == "tipo do documento: ASO"


def test_saude_por_lexico_exige_mais_de_um_termo():
    um = privacidade.analisar_documento("CONTRATO", "O diagnóstico do cenário econômico é incerto.")
    assert um.sensiveis == {}                                  # uma palavra solta não marca
    dois = privacidade.analisar_documento("OUTRO", "LAUDO MÉDICO: prontuário 123, internação em 2024")
    assert set(dois.sensiveis) == {"SAUDE"}
    assert {"laudo medico", "prontuario", "internacao"} <= set(dois.sensiveis["SAUDE"])    # evidência sem acento


def test_termo_so_conta_como_palavra_inteira():
    # "crm" dentro de outra palavra, "cirurgias" etc. não podem disparar
    assert privacidade.analisar_documento("OUTRO", "scrmx diagnosticos cirurgias").sensiveis == {}


def test_biometria_e_sindical_bastam_com_um_termo_especifico():
    a = privacidade.analisar_documento("CONTRACHEQUE", "Desconto: contribuição sindical R$ 30; impressão digital")
    assert set(a.sensiveis) == {"SINDICAL", "BIOMETRIA"}


def test_nivel_de_risco():
    assert privacidade.nivel_de_risco(2, 5)[0] == "alto"
    assert privacidade.nivel_de_risco(0, 5)[0] == "medio"
    assert privacidade.nivel_de_risco(0, 0)[0] == "baixo"


# ---------------------------------------------------------------- endpoint (lote montado direto no banco, sem OCR)
@pytest.fixture()
def lote_montado():
    from fastapi.testclient import TestClient

    from app.main import app

    lote_id = novo_id()
    textos = [
        ("ASO", "Atestado de Saúde Ocupacional [NOME] CPF [CPF] médico do trabalho [NOME]"),
        ("CONTRATO", "Contratante [NOME] CPF [CPF] [ENDERECO] [CEP]. O diagnóstico do projeto é favorável."),
        ("OUTRO", "Laudo médico e prontuário de [NOME], CPF [CPF] e [CPF]"),
        ("NOTA_FISCAL", "Emitente [CNPJ] valor total 100,00"),
    ]
    with TestClient(app) as c, SessionLocal() as db:       # subir a API primeiro: é ela que cria as tabelas
        db.add(Lote(id=lote_id, nome="lote-privacidade.pdf", arquivo_key=f"lotes/{lote_id}/o.pdf",
                    hash_sha256=lote_id * 2, mime="application/pdf", tamanho_bytes=1, total_paginas=4,
                    status=StatusLote.CONCLUIDO))
        db.flush()
        for i, (tipo, texto) in enumerate(textos):
            d = Documento(lote_id=lote_id, ordem=i, tipo=tipo, pagina_inicio=i, pagina_fim=i, confianca=0.9,
                          status_revisao="pendente" if i == 3 else "auto_aprovado", texto=texto, titulo=f"doc {i}")
            db.add(d)
            db.flush()
            # duas pessoas distintas no lote inteiro (aaa aparece em 2 páginas)
            cpfs = {0: [{"h": "aaa", "m": "x"}], 1: [{"h": "aaa", "m": "x"}], 2: [{"h": "bbb", "m": "y"}]}.get(i, [])
            db.add(Pagina(lote_id=lote_id, numero=i, documento_id=d.id, status="ok", sinais={"cpfs": cpfs}))
        db.commit()
        yield c, lote_id


def test_relatorio_do_lote(lote_montado):
    c, lote_id = lote_montado
    r = c.get(f"/lotes/{lote_id}/privacidade")
    assert r.status_code == 200, r.text
    rel = r.json()

    assert rel["nivel_risco"] == "alto"
    t = rel["totais"]
    assert t["documentos"] == 4 and t["documentos_com_dados_pessoais"] == 3
    assert t["documentos_com_dados_sensiveis"] == 2 and t["pessoas_distintas"] == 2 and t["documentos_em_revisao"] == 1

    ident = rel["identificadores"]
    assert ident["CPF"]["ocorrencias"] == 4 and ident["CPF"]["documentos"] == 3 and ident["CPF"]["pessoas_distintas"] == 2
    assert ident["NOME"]["ocorrencias"] == 4 and ident["ENDERECO"]["ocorrencias"] == 1 and ident["CNPJ"]["ocorrencias"] == 1

    saude = rel["dados_sensiveis"]["SAUDE"]
    assert saude["documentos"] == 2 and saude["por_tipo"] == {"ASO": 1, "OUTRO": 1}
    assert {d["tipo"] for d in rel["documentos_sensiveis"]} == {"ASO", "OUTRO"}      # o contrato (1 termo) não entra
    assert "4 CPF(s) (2 pessoa(s) distinta(s))" in rel["resumo"] and "2 documento(s) com dados de saúde" in rel["resumo"]
    assert any("fila de revisão" in x for x in rel["recomendacoes"])


def test_relatorio_nao_devolve_dado_pessoal(lote_montado):
    c, lote_id = lote_montado
    corpo = json.dumps(c.get(f"/lotes/{lote_id}/privacidade").json(), ensure_ascii=False)
    assert "aaa" not in corpo and "bbb" not in corpo          # impressões digitais de CPF não saem da API


def test_limite_trunca_a_lista_de_documentos(lote_montado):
    c, lote_id = lote_montado
    rel = c.get(f"/lotes/{lote_id}/privacidade", params={"limite": 1}).json()
    assert len(rel["documentos_sensiveis"]) == 1 and rel["documentos_sensiveis_truncado"] is True
    assert rel["totais"]["documentos_com_dados_sensiveis"] == 2          # o total continua certo


def test_lote_inexistente_e_lote_nao_concluido(lote_montado):
    c, lote_id = lote_montado
    assert c.get("/lotes/nao-existe/privacidade").status_code == 404
    with SessionLocal() as db:
        db.get(Lote, lote_id).status = StatusLote.PROCESSANDO
        db.commit()
    assert c.get(f"/lotes/{lote_id}/privacidade").status_code == 409


def test_lote_sem_dado_pessoal_e_risco_baixo():
    from fastapi.testclient import TestClient

    from app.main import app

    lote_id = novo_id()
    with TestClient(app) as c, SessionLocal() as db:
        db.add(Lote(id=lote_id, nome="vazio.pdf", arquivo_key="k", hash_sha256=lote_id * 2, mime="application/pdf",
                    tamanho_bytes=1, total_paginas=1, status=StatusLote.CONCLUIDO))
        db.flush()
        db.add(Documento(lote_id=lote_id, ordem=0, tipo="NOTA_FISCAL", pagina_inicio=0, pagina_fim=0,
                         confianca=0.9, status_revisao="auto_aprovado", texto="Emitente [CNPJ] total 10,00"))
        db.commit()
        rel = c.get(f"/lotes/{lote_id}/privacidade").json()
    assert rel["nivel_risco"] == "baixo" and rel["totais"]["pessoas_distintas"] == 0
    assert "CNPJ" in rel["identificadores"] and rel["identificadores"]["CNPJ"]["ocorrencias"] == 1
    assert "não tem dados pessoais" in rel["resumo"]


def test_relatorio_no_lote_real_de_terceiros(lote_terceiros):
    """Pipeline completo (OCR + anonimização): o ASO do lote precisa aparecer como dado de saúde."""
    c, lote = lote_terceiros
    rel = c.get(f"/lotes/{lote['id']}/privacidade").json()
    assert rel["totais"]["documentos"] > 0 and rel["totais"]["pessoas_distintas"] == 2     # 2 trabalhadores no lote
    assert rel["identificadores"]["CPF"]["ocorrencias"] >= 2
    assert rel["dados_sensiveis"]["SAUDE"]["documentos"] >= 1 and "ASO" in rel["dados_sensiveis"]["SAUDE"]["por_tipo"]
    assert rel["nivel_risco"] == "alto"
