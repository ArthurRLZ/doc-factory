"""Abstração de storage de arquivos.

Local (disco) no MVP; S3/MinIO em produção — o resto do código não muda.
Layout das chaves:
    lotes/{lote_id}/original.pdf
    lotes/{lote_id}/paginas/00012.png | 00012.thumb.jpg | 00012.palavras.json
    lotes/{lote_id}/documentos/{doc_id}.pdf | {doc_id}.anon.pdf
"""
import json
import os
import shutil
from functools import lru_cache
from pathlib import Path

from app.config import settings


class Storage:
    def put_file(self, key: str, caminho: str) -> None: ...
    def put_bytes(self, key: str, dados: bytes, content_type: str = "application/octet-stream") -> None: ...
    def get_bytes(self, key: str) -> bytes: ...
    def caminho_local(self, key: str) -> str: ...     # baixa p/ cache se for remoto
    def delete(self, key: str) -> None: ...
    def delete_prefixo(self, prefixo: str) -> None: ...   # apaga tudo sob o prefixo (ex.: um lote)

    def put_json(self, key: str, obj) -> None:
        self.put_bytes(key, json.dumps(obj, ensure_ascii=False).encode(), "application/json")

    def get_json(self, key: str):
        return json.loads(self.get_bytes(key))


class LocalStorage(Storage):
    def __init__(self, raiz: str):
        self.raiz = Path(raiz) / "storage"
        self.raiz.mkdir(parents=True, exist_ok=True)

    def _p(self, key: str) -> Path:
        p = (self.raiz / key).resolve()
        if self.raiz.resolve() not in p.parents:      # bloqueia path traversal
            raise ValueError("chave inválida")
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def put_file(self, key, caminho):
        shutil.copyfile(caminho, self._p(key))

    def put_bytes(self, key, dados, content_type="application/octet-stream"):
        tmp = self._p(key).with_suffix(".tmp")
        tmp.write_bytes(dados)
        os.replace(tmp, self._p(key))                 # escrita atômica

    def get_bytes(self, key):
        return self._p(key).read_bytes()

    def caminho_local(self, key):
        return str(self._p(key))

    def delete(self, key):
        self._p(key).unlink(missing_ok=True)

    def delete_prefixo(self, prefixo):
        alvo = (self.raiz / prefixo).resolve()
        if self.raiz.resolve() not in alvo.parents:
            raise ValueError("prefixo inválido")
        shutil.rmtree(alvo, ignore_errors=True)


class S3Storage(Storage):
    """MinIO / AWS S3 / qualquer compatível com S3."""

    def __init__(self):
        import boto3  # import tardio: só exige boto3 se usar S3
        self.bucket = settings.S3_BUCKET
        self.s3 = boto3.client("s3", endpoint_url=settings.S3_ENDPOINT,
                               aws_access_key_id=settings.S3_ACCESS_KEY,
                               aws_secret_access_key=settings.S3_SECRET_KEY)
        try:
            self.s3.head_bucket(Bucket=self.bucket)
        except Exception:                                  # bucket ainda não existe
            self.s3.create_bucket(Bucket=self.bucket)
        self.cache = Path(settings.DATA_DIR) / "cache"
        self.cache.mkdir(parents=True, exist_ok=True)

    def put_file(self, key, caminho):
        self.s3.upload_file(caminho, self.bucket, key)   # multipart automático p/ arquivos grandes

    def put_bytes(self, key, dados, content_type="application/octet-stream"):
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=dados, ContentType=content_type)

    def get_bytes(self, key):
        return self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def caminho_local(self, key):
        destino = self.cache / key
        if not destino.exists():
            destino.parent.mkdir(parents=True, exist_ok=True)
            self.s3.download_file(self.bucket, key, str(destino))
        return str(destino)

    def delete(self, key):
        self.s3.delete_object(Bucket=self.bucket, Key=key)

    def delete_prefixo(self, prefixo):
        for pagina in self.s3.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=prefixo):
            chaves = [{"Key": o["Key"]} for o in pagina.get("Contents", [])]
            if chaves:
                self.s3.delete_objects(Bucket=self.bucket, Delete={"Objects": chaves})
        shutil.rmtree(self.cache / prefixo, ignore_errors=True)


@lru_cache
def get_storage() -> Storage:
    if settings.STORAGE_BACKEND == "s3":
        return S3Storage()
    return LocalStorage(settings.DATA_DIR)


# helpers de chave (um lugar só)
def key_original(lote_id: str, ext: str) -> str:
    return f"lotes/{lote_id}/original{ext}"


def key_pagina(lote_id: str, numero: int, sufixo: str) -> str:
    return f"lotes/{lote_id}/paginas/{numero:05d}{sufixo}"


def key_documento(lote_id: str, doc_id: str, anon: bool = False) -> str:
    return f"lotes/{lote_id}/documentos/{doc_id}{'.anon' if anon else ''}.pdf"
