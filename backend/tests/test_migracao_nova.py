"""Banco de uma versão anterior sobe sem erro: migrar_colunas() adiciona as colunas novas das etapas F0–F9."""
from sqlalchemy import create_engine, text

# colunas acrescentadas a tabelas JÁ EXISTENTES (tabelas novas são criadas por create_all)
NOVAS = [
    "lotes.llm_chamadas_classificacao", "lotes.llm_chamadas_resumo", "lotes.llm_chamadas_outras",
    "lotes.llm_paginas", "lotes.gabarito", "lotes.regras_aplicadas", "lotes.origem", "lotes.convite_id",
    "paginas.llm_chamado",
    "documentos.decidido_por", "documentos.ia_justificativa", "documentos.regras_aplicadas", "documentos.pre_revisao",
    "trabalhadores.funcao", "trabalhadores.funcao_chave", "trabalhadores.funcao_origem", "trabalhadores.funcao_evidencia",
]


def test_banco_antigo_ganha_colunas_novas(tmp_path, monkeypatch):
    import app.db as db_mod
    import app.models  # noqa: F401  (registra as tabelas no metadata)
    antigo = create_engine(f"sqlite:///{tmp_path}/antigo.db")
    with antigo.begin() as conn:   # esquema mínimo como era antes das etapas F0–F9
        conn.execute(text("CREATE TABLE lotes (id VARCHAR(32) PRIMARY KEY, nome VARCHAR(255), arquivo_key VARCHAR(512), "
                          "hash_sha256 VARCHAR(64), mime VARCHAR(100), tamanho_bytes INTEGER, total_paginas INTEGER, "
                          "status VARCHAR(20), erro TEXT, criado_em DATETIME, atualizado_em DATETIME)"))
        conn.execute(text("CREATE TABLE paginas (id INTEGER PRIMARY KEY, lote_id VARCHAR(32), numero INTEGER, "
                          "status VARCHAR(20))"))
        conn.execute(text("CREATE TABLE documentos (id VARCHAR(32) PRIMARY KEY, lote_id VARCHAR(32), ordem INTEGER, "
                          "tipo VARCHAR(50), pagina_inicio INTEGER, pagina_fim INTEGER, confianca FLOAT, "
                          "status_revisao VARCHAR(20))"))
        conn.execute(text("CREATE TABLE trabalhadores (id INTEGER PRIMARY KEY, cpf_hash VARCHAR(64), "
                          "cpf_mascarado VARCHAR(20), criado_em DATETIME)"))
        conn.execute(text("INSERT INTO lotes (id, nome, total_paginas) VALUES ('l1', 'antigo', 14)"))
        conn.execute(text("INSERT INTO paginas (id, lote_id, numero, status) VALUES (1, 'l1', 0, 'ok')"))
    monkeypatch.setattr(db_mod, "engine", antigo)

    adicionadas = db_mod.migrar_colunas()
    assert set(NOVAS) <= set(adicionadas), set(NOVAS) - set(adicionadas)
    with antigo.connect() as conn:
        assert conn.execute(text("SELECT llm_paginas FROM lotes WHERE id='l1'")).scalar() == 0      # default aplicado
        assert not conn.execute(text("SELECT llm_chamado FROM paginas WHERE id=1")).scalar()
    assert db_mod.migrar_colunas() == []                                                          # idempotente
