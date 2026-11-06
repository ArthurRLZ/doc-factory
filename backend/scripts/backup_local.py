"""Cópia e restauração offline do SQLite e do armazenamento local.

Pare a API e todos os workers antes de criar a cópia. A restauração só escreve
em um diretório novo, para nunca substituir dados existentes.
"""
import argparse
import hashlib
import json
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from pathlib import Path, PurePosixPath


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def criar(data, saida):
    data, saida = data.resolve(), saida.resolve()
    if not (data / "docfactory.db").is_file():
        raise ValueError("Banco docfactory.db não encontrado")
    if saida.exists():
        raise ValueError("O arquivo de destino já existe")
    if data == saida.parent or data in saida.parents:
        raise ValueError("A cópia deve ficar fora da pasta de dados")
    with tempfile.TemporaryDirectory(prefix="docfactory-backup-") as tmp:
        stage = Path(tmp)
        with closing(sqlite3.connect(f"file:{(data / 'docfactory.db').as_posix()}?mode=ro", uri=True)) as src:
            with closing(sqlite3.connect(stage / "docfactory.db")) as dst:
                src.backup(dst)
        if (data / "storage").exists():
            if (data / "storage").is_symlink() or any(p.is_symlink() for p in (data / "storage").rglob("*")):
                raise ValueError("Links simbólicos não são suportados na cópia")
            shutil.copytree(data / "storage", stage / "storage", symlinks=False)
        arquivos = {}
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                arquivos[path.relative_to(stage).as_posix()] = digest(path)
        saida.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(saida, "x", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            for nome in arquivos:
                z.write(stage / nome, nome)
            z.writestr("manifesto_backup.json", json.dumps({"versao": 1, "sha256": arquivos}, ensure_ascii=False))
    return len(arquivos)


def restaurar(arquivo, destino):
    arquivo, destino = arquivo.resolve(), destino.resolve()
    if destino.exists():
        raise ValueError("O destino já existe; escolha um diretório novo")
    with tempfile.TemporaryDirectory(prefix="docfactory-restore-", dir=destino.parent) as tmp:
        stage = Path(tmp) / "dados"
        stage.mkdir()
        with zipfile.ZipFile(arquivo) as z:
            nomes = z.namelist()
            if len(nomes) != len(set(nomes)) or "manifesto_backup.json" not in nomes:
                raise ValueError("Cópia inválida ou com nomes duplicados")
            manifesto = json.loads(z.read("manifesto_backup.json"))
            arquivos = manifesto.get("sha256", {})
            if manifesto.get("versao") != 1 or "docfactory.db" not in arquivos or set(nomes) != set(arquivos) | {"manifesto_backup.json"}:
                raise ValueError("Manifesto inválido")
            for nome, esperado in arquivos.items():
                partes = PurePosixPath(nome)
                if partes.is_absolute() or ".." in partes.parts or "\\" in nome or ":" in nome or not (nome == "docfactory.db" or nome.startswith("storage/")):
                    raise ValueError("Caminho inválido na cópia")
                alvo = stage.joinpath(*partes.parts)
                alvo.parent.mkdir(parents=True, exist_ok=True)
                with z.open(nome) as src, alvo.open("xb") as dst:
                    shutil.copyfileobj(src, dst, 1024 * 1024)
                if digest(alvo) != esperado:
                    raise ValueError(f"Arquivo corrompido: {nome}")
        with closing(sqlite3.connect(stage / "docfactory.db")) as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("O banco restaurado falhou na verificação de integridade")
        stage.rename(destino)
    return len(arquivos)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="acao", required=True)
    b = sub.add_parser("criar")
    b.add_argument("--dados", type=Path, required=True)
    b.add_argument("--saida", type=Path, required=True)
    b.add_argument("--offline-confirmado", action="store_true", required=True,
                   help="Confirme que API e workers estão parados")
    r = sub.add_parser("restaurar")
    r.add_argument("--arquivo", type=Path, required=True)
    r.add_argument("--destino", type=Path, required=True)
    args = parser.parse_args()
    n = criar(args.dados, args.saida) if args.acao == "criar" else restaurar(args.arquivo, args.destino)
    print(f"Concluído: {n} arquivos.")
