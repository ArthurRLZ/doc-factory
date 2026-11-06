"""F3: função do trabalhador → NRs exigidas no checklist (regra primeiro, IA validada, correção manual)."""
from datetime import timedelta

import pytest

from app import util
from app.config import settings
from app.models import Documento, Trabalhador
from app.pipeline import checklist, funcao

HOJE = util.hoje()


def test_extrair_por_regra():
    r = funcao.extrair_funcao_por_regra("ATESTADO DE SAÚDE OCUPACIONAL\nNome: [NOME]\nFunção: Eletricista de manutenção\n")
    assert r == ("Eletricista de manutenção", "Função: Eletricista de manutenção")
    assert funcao.mapear_funcao(r[0]) == "eletricista"
    assert funcao.extrair_funcao_por_regra("documento sem rótulo de cargo") is None
    assert funcao.mapear_funcao("Auxiliar administrativo") is None


class _IA:
    def __init__(self, resposta):
        self.resposta = resposta

    def extrair_funcao(self, texto, funcoes):
        return self.resposta


TEXTO = "ASO\nO empregado atua como eletricista de redes na obra."


def test_ia_validada():
    ok = funcao.extrair_funcao_por_llm(_IA({"funcao": "eletricista de redes", "chave": "eletricista",
                                            "evidencia": "atua como eletricista de redes"}), TEXTO)
    assert ok == ("eletricista de redes", "eletricista", "atua como eletricista de redes")
    inventada = _IA({"funcao": "soldador", "chave": "soldador", "evidencia": "trabalha como soldador"})
    assert funcao.extrair_funcao_por_llm(inventada, TEXTO) is None                     # evidência não existe
    fora = _IA({"funcao": "astronauta", "chave": "astronauta", "evidencia": "atua como eletricista de redes"})
    assert funcao.extrair_funcao_por_llm(fora, TEXTO) is None                          # chave fora da lista


def test_atualizar_funcao_usa_ia_quando_nao_ha_rotulo():
    t = Trabalhador(id=1, cpf_hash="x", cpf_mascarado="***")
    d = Documento(tipo="ASO", texto=TEXTO, trabalhador_id=1)
    funcao.atualizar_funcao(None, t, [d], _IA({"funcao": "eletricista de redes", "chave": "eletricista",
                                               "evidencia": "atua como eletricista de redes"}))
    assert t.funcao_chave == "eletricista" and t.funcao_origem == "ia"
    t.funcao_origem, t.funcao_chave = "manual", None                                   # manual não é sobrescrito
    funcao.atualizar_funcao(None, t, [d], _IA({"funcao": "x", "chave": "eletricista", "evidencia": TEXTO}))
    assert t.funcao_chave is None


def _cert(nr: str, dias: int) -> Documento:
    return Documento(id=f"c{nr}", tipo="CERTIFICADO_NR", campos={"norma": nr}, texto=f"treinamento {nr}",
                     validade_data=HOJE + timedelta(days=dias))


def _eletricista(*certs) -> Trabalhador:
    t = Trabalhador(id=9, cpf_hash="h", cpf_mascarado="***.000.000-**", funcao="Eletricista", funcao_chave="eletricista")
    t.documentos = list(certs)
    return t


def test_checklist_exige_nr_da_funcao():
    c = checklist.avaliar(_eletricista(_cert("NR-35", 300)))
    assert "CERTIFICADO_NR:NR-10" in c["faltando"] and "CERTIFICADO_NR:NR-35" not in c["faltando"]
    item = next(i for i in c["checklist"] if i["tipo"] == "CERTIFICADO_NR:NR-10")
    assert item["motivo_exigencia"] == "exigido para a função Eletricista" and item["tipo_nome"] == "Certificado NR-10"
    assert c["outros_alertas"] == []                     # o NR-35 já coberto não aparece de novo


def test_checklist_nrs_vigentes_ficam_ok():
    c = checklist.avaliar(_eletricista(_cert("NR-35", 300), _cert("NR-10", 300)))
    nrs = {i["tipo"]: i["status"] for i in c["checklist"] if i["tipo"].startswith("CERTIFICADO_NR:")}
    assert nrs == {"CERTIFICADO_NR:NR-10": "ok", "CERTIFICADO_NR:NR-35": "ok"}


def test_flag_desligada_volta_ao_checklist_fixo(monkeypatch):
    monkeypatch.setattr(settings, "FUNCAO_EXIGENCIAS_ATIVO", False)
    c = checklist.avaliar(_eletricista(_cert("NR-35", 300)))
    assert c["exigidos"] == ["IDENTIDADE", "CTPS", "ASO", "FICHA_EPI"]
    assert not any("motivo_exigencia" in i for i in c["checklist"])


# ---------------------------------------------------------------- lote Bernhoeft (B é eletricista)
@pytest.fixture()
def eletricista(lote_terceiros):
    c, lote = lote_terceiros
    ts = c.get("/trabalhadores", params={"lote_id": lote["id"]}).json()["itens"]
    return c, next(t for t in ts if t["funcao_chave"] == "eletricista"), ts


def test_dossie_do_eletricista(eletricista):
    c, t, todos = eletricista
    assert t["funcao"] == "Eletricista" and t["funcao_origem"] == "texto"
    d = c.get(f"/trabalhadores/{t['id']}/dossie").json()
    itens = {i["tipo"]: i for i in d["checklist"]}
    assert itens["CERTIFICADO_NR:NR-10"]["status"] == "vencendo"            # o certificado do gerador vence logo
    assert itens["CERTIFICADO_NR:NR-35"]["status"] == "faltando"
    assert itens["CERTIFICADO_NR:NR-35"]["motivo_exigencia"] == "exigido para a função Eletricista"
    assert any(x["funcao_texto"] == "Auxiliar administrativo" and x["funcao_chave"] is None for x in todos)


def test_corrigir_funcao_manual(eletricista):
    c, t, _ = eletricista
    assert c.put(f"/trabalhadores/{t['id']}/funcao", json={"funcao_chave": "astronauta"}).status_code == 422
    r = c.put(f"/trabalhadores/{t['id']}/funcao", json={"funcao_chave": "soldador"})
    assert r.status_code == 200 and r.json()["funcao_origem"] == "manual"
    assert "CERTIFICADO_NR:NR-18" in r.json()["exigidos"]
    r = c.put(f"/trabalhadores/{t['id']}/funcao", json={"funcao_chave": "eletricista"})   # volta para os outros testes
    assert r.json()["funcao"] == "Eletricista"
    assert {f["chave"] for f in c.get("/funcoes").json()} >= {"eletricista", "soldador"}
