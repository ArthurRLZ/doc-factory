import importlib.util
import sqlite3
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("backup_local", Path(__file__).parents[1] / "scripts" / "backup_local.py")
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


def test_copia_e_restauracao_sem_sobrescrever(tmp_path):
    data = tmp_path / "data"
    (data / "storage" / "lotes").mkdir(parents=True)
    with sqlite3.connect(data / "docfactory.db") as db:
        db.execute("create table lotes (nome text)")
        db.execute("insert into lotes values ('teste')")
    (data / "storage" / "lotes" / "arquivo.bin").write_bytes(b"lote de teste")
    arquivo, destino = tmp_path / "copia.zip", tmp_path / "restaurado"
    assert backup.criar(data, arquivo) == 2
    assert backup.restaurar(arquivo, destino) == 2
    with sqlite3.connect(destino / "docfactory.db") as db:
        assert db.execute("select nome from lotes").fetchone() == ("teste",)
    assert (destino / "storage" / "lotes" / "arquivo.bin").read_bytes() == b"lote de teste"
    with pytest.raises(ValueError):
        backup.restaurar(arquivo, destino)
