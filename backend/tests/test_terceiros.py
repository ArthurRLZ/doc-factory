"""Lote de gestão de terceiros: documentos trabalhistas e de regularidade da empresa."""

ESPERADO = [  # (tipo, página inicial, página final) — 0-based; a página 7 é o separador em branco
    ("ASO", 0, 0), ("FICHA_EPI", 1, 1), ("CERTIFICADO_NR", 2, 2), ("CONTRACHEQUE", 3, 3),
    ("CTPS", 4, 4), ("ASO", 5, 5), ("CERTIFICADO_NR", 6, 6),
    ("CND_FEDERAL", 8, 8), ("CRF_FGTS", 9, 9), ("CNDT", 10, 10), ("CONTRATO", 11, 12), ("GUIA_FGTS", 13, 13),
]


def test_tipos_de_terceiros_separados_e_classificados(lote_terceiros):
    c, lote = lote_terceiros
    docs = c.get(f"/lotes/{lote['id']}/documentos").json()
    obtido = [(d["tipo"], d["pagina_inicio"], d["pagina_fim"]) for d in docs]
    for d in docs:
        print(d["tipo"], d["pagina_inicio"], d["pagina_fim"], d["confianca"], d["status_revisao"], d["motivos"])
    assert obtido == ESPERADO


def test_tipos_listam_descricao_e_validade(processado):
    c, _ = processado
    tipos = {t["codigo"]: t for t in c.get("/tipos").json()}
    assert len(tipos) >= 14
    assert tipos["ASO"]["descricao"] and tipos["CRF_FGTS"]["validade"] == {"dias": 30}
