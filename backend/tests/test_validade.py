"""Validade / vigência: texto, modelo (com evidência conferida), regra do tipo, status e vencimentos."""
from datetime import date, timedelta

from app import util
from app.pipeline import validade as v

HOJE = util.hoje()      # mesmo "hoje" do sistema (fuso configurado), não o relógio do servidor


def test_data_escrita_no_texto():
    r = v.validade_no_texto("Emitida em 01/09/2026. Válida até 15/03/2027.")
    assert r.data == date(2027, 3, 15) and r.origem == "texto" and "Válida até" in r.evidencia


def test_intervalo_usa_a_data_final():
    assert v.validade_no_texto("Validade: 01/10/2026 a 31/10/2026").data == date(2026, 10, 31)


def test_vigencia_por_extenso_calcula_o_fim():
    r = v.validade_no_texto("o contrato terá vigência de 12 (doze) meses a partir de 05/11/2026.")
    assert r.data == date(2027, 11, 5) and r.inicio == date(2026, 11, 5)
    assert v.validade_no_texto("vigência de 30 dias contados de 1 de março de 2026").data == date(2026, 3, 31)


def test_regra_do_tipo_e_por_nr():
    aso = v.avaliar("ASO", "Data do exame: 10/01/2026\nResultado: APTO")
    assert aso.data == date(2027, 1, 10) and aso.origem == "regra" and "12 meses" in aso.evidencia
    nr33 = v.avaliar("CERTIFICADO_NR", "treinamento de NR-33\nData de conclusão: 10/01/2026")
    assert nr33.data == date(2027, 1, 10)            # NR-33: reciclagem anual
    nr35 = v.avaliar("CERTIFICADO_NR", "treinamento de NR-35\nData de conclusão: 10/01/2026")
    assert nr35.data == date(2028, 1, 10)            # NR-35: a cada 2 anos


def test_modelo_aceito_so_com_evidencia_real():
    texto = "A vigência é de doze meses, iniciando em cinco de novembro de 2026."
    ok = v.avaliar("CONTRATO", texto, {"data": "05/11/2027", "evidencia": "vigência é de doze meses, iniciando em"})
    assert ok.data == date(2027, 11, 5) and ok.origem == "modelo"
    inventado = v.avaliar("CONTRATO", texto, {"data": "05/11/2027", "evidencia": "válido até 05/11/2027"})
    assert inventado.data is None                    # trecho não existe no texto → descartado


def test_texto_e_modelo_divergentes_vao_para_revisao():
    r = v.avaliar("CND_FEDERAL", "Válida até 15/03/2027.", {"data": "15/04/2027", "evidencia": "Válida até 15/03/2027"})
    assert r.data == date(2027, 3, 15) and any("divergentes" in m for m in r.motivos)


def test_obrigatoria_sem_data_vai_para_revisao_e_tipo_sem_validade_ignora():
    assert v.avaliar("ASO", "Resultado: APTO").motivos == ["validade não identificada no documento"]
    assert v.avaliar("CTPS", "Validade: 01/01/2020").data is None       # CTPS não vence
    assert v.avaliar("GUIA_FGTS", "Pagar até: 10/12/2026").data is None  # vencimento de pagamento não é validade


def test_status():
    assert v.status(HOJE - timedelta(days=1), "ASO") == ("vencido", -1)
    assert v.status(HOJE + timedelta(days=10), "ASO") == ("vencendo", 10)
    assert v.status(HOJE + timedelta(days=90), "ASO")[0] == "vigente"
    assert v.status(None, "ASO")[0] == "indeterminado" and v.status(None, "CTPS")[0] == "sem_validade"


def test_lote_terceiros_status_esperados(lote_terceiros):
    c, lote = lote_terceiros
    docs = c.get(f"/lotes/{lote['id']}/documentos").json()
    st = [(d["tipo"], d["validade"]["status"], d["validade"]["origem"]) for d in docs]
    for d in docs:
        print(d["tipo"], d["validade"], d["prioridade"], d["prioridade_motivo"])
    assert st == [
        ("ASO", "vencido", "regra"), ("FICHA_EPI", "sem_validade", None), ("CERTIFICADO_NR", "vigente", "regra"),
        ("CONTRACHEQUE", "sem_validade", None), ("CTPS", "sem_validade", None), ("ASO", "vigente", "regra"),
        ("CERTIFICADO_NR", "vencendo", "regra"), ("CND_FEDERAL", "vigente", "texto"), ("CRF_FGTS", "vencido", "texto"),
        ("CNDT", "vencendo", "texto"), ("CONTRATO", "vencendo", "texto"), ("GUIA_FGTS", "sem_validade", None),
    ]
    vencidos = [d for d in docs if d["validade"]["status"] in ("vencido", "vencendo")]
    assert all(d["prioridade"] == "alta" for d in vencidos)
    assert all(d["setor"] and d["titulo"] and d["codigo"].startswith("DOC-") for d in docs)


def test_rota_vencimentos(lote_terceiros):
    c, lote = lote_terceiros
    itens = c.get("/vencimentos", params={"lote_id": lote["id"], "ate_dias": 30}).json()
    datas = [i["validade"]["data"] for i in itens]
    assert datas == sorted(datas) and len(itens) == 5      # 2 vencidos + 3 vencendo
    so_futuros = c.get("/vencimentos", params={"lote_id": lote["id"], "incluir_vencidos": False}).json()
    assert all(i["validade"]["status"] == "vencendo" for i in so_futuros) and len(so_futuros) == 3
