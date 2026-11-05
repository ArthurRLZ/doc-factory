"""Contratos da API (o que o front recebe/envia)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    nome: str
    status: str
    total_paginas: int
    paginas_processadas: int = 0
    progresso: float = 0.0
    tamanho_bytes: int
    hash_sha256: str
    erro: str | None = None
    criado_em: datetime


class PaginaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    numero: int
    status: str
    documento_id: str | None
    tipo: str | None
    confianca: float | None
    tipo_regra: str | None
    tipo_llm: str | None
    ocr_confianca: float | None
    em_branco: bool
    nativa: bool
    sinais: dict | None
    tentativas: int
    erro: str | None


class DocumentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    lote_id: str
    ordem: int
    tipo: str
    tipo_nome: str = ""
    pagina_inicio: int
    pagina_fim: int
    n_paginas: int = 0
    confianca: float
    status_revisao: str
    motivos: list[str] | None


class RevisaoIn(BaseModel):
    acao: Literal["aprovar", "alterar_tipo", "dividir", "juntar_proximo"]
    usuario: str = Field(min_length=1, max_length=100)
    tipo: str | None = None              # para alterar_tipo
    pagina_corte: int | None = None      # para dividir: nº (0-based) da 1ª página do novo documento


class BuscaItem(BaseModel):
    documento_id: str
    lote_id: str
    tipo: str
    trecho: str
