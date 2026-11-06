"""F5: % de acerto contra gabarito (cortes, documentos exatos, tipo, erros silenciosos)."""
import os
import sys

from app.pipeline.avaliacao import comparar
from tests.conftest import BASE

sys.path.insert(0, os.path.join(BASE, "scripts"))
import gerar_lote_bernhoeft  # noqa: E402

GAB = [{"tipo": "ASO", "paginas": [0]}, {"tipo": "CONTRATO", "paginas": [2, 3]}, {"tipo": "CNDT", "paginas": [4]}]


def _prev(*docs, status="auto_aprovado"):
    return [{"id": f"d{i}", "tipo": t, "paginas": p, "status_revisao": status} for i, (t, p) in enumerate(docs)]


def test_perfeito():
    m = comparar(GAB, _prev(("ASO", [0]), ("CONTRATO", [2, 3]), ("CNDT", [4])))
    assert m["corte_f1"] == m["documentos_exatos_pct"] == m["tipo_acerto_pct"] == 100.0
    assert m["erros_silenciosos"] == [] and m["detalhes"] == [] and m["acerto_dos_automatizados_pct"] == 100.0


def test_corte_faltando():
    m = comparar(GAB, _prev(("ASO", [0]), ("CONTRATO", [2, 3, 4])))      # CNDT engolida pelo contrato
    assert m["corte_precisao"] == 100.0 and m["corte_revocacao"] == 66.7
    assert m["documentos_exatos_pct"] == 33.3
    assert any("CNDT pág 5" in d for d in m["detalhes"])


def test_corte_extra():
    m = comparar(GAB, _prev(("ASO", [0]), ("CONTRATO", [2]), ("DESCONHECIDO", [3]), ("CNDT", [4])))
    assert m["corte_revocacao"] == 100.0 and m["corte_precisao"] == 75.0
    assert "gabarito: CONTRATO págs 3–4 · sistema: CONTRATO pág 3 + DESCONHECIDO pág 4" in m["detalhes"]


def test_tipo_errado_e_erro_silencioso():
    m = comparar(GAB, _prev(("CTPS", [0]), ("CONTRATO", [2, 3]), ("CNDT", [4])))
    assert m["tipo_acerto_pct"] == 66.7 and m["corte_f1"] == 100.0
    assert m["erros_silenciosos"] == [{"id": "d0", "tipo_previsto": "CTPS", "paginas": [0]}]


def test_erro_em_revisao_nao_e_silencioso():
    m = comparar(GAB, _prev(("CTPS", [0]), status="pendente"))
    assert m["erros_silenciosos"] == [] and m["automatizados_pct"] == 0.0 and m["acerto_dos_automatizados_pct"] is None


def _gabarito_bernhoeft():
    g = gerar_lote_bernhoeft
    return g.montar_gabarito(g.PAGINAS, g.TIPO_DO_TITULO, "terceiros.pdf")


def test_lote_bernhoeft_acerta_tudo(lote_terceiros):
    c, lote = lote_terceiros
    assert c.get(f"/lotes/{lote['id']}/avaliacao").status_code == 409            # ainda sem gabarito
    assert c.put(f"/lotes/{lote['id']}/gabarito", json=_gabarito_bernhoeft()).status_code == 200
    r = c.get(f"/lotes/{lote['id']}/avaliacao")
    assert r.status_code == 200, r.text
    m = r.json()["metricas"]
    assert m["corte_f1"] == 100.0 and m["tipo_acerto_pct"] == 100.0 and m["erros_silenciosos"] == []


def test_gabarito_invalido(lote_terceiros):
    c, lote = lote_terceiros
    url = f"/lotes/{lote['id']}/gabarito"
    assert c.put(url, json={"documentos": [{"tipo": "INVENTADO", "paginas": [0]}]}).status_code == 422
    assert c.put(url, json={"documentos": [{"tipo": "ASO", "paginas": [99]}]}).status_code == 422
    assert c.put(url, json={"documentos": [{"tipo": "ASO", "paginas": [0]},
                                           {"tipo": "CTPS", "paginas": [0]}]}).status_code == 422
    assert c.put("/lotes/naoexiste/gabarito", json=_gabarito_bernhoeft()).status_code == 404
