"""Contratos da API (o que o front recebe/envia)."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.tipos import PRIORIDADE_NOME

Prioridade = Literal["baixa", "media", "alta"]


def _prioridade_texto(v):
    """No banco a prioridade é número (1-3); na API é texto."""
    if isinstance(v, int):
        return PRIORIDADE_NOME.get(v, "media")
    return v or "media"


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
    prioridade: str = "media"
    enviado_por: str | None = None
    erro: str | None = None
    criado_em: datetime

    _p = field_validator("prioridade", mode="before")(_prioridade_texto)


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


class ValidadeOut(BaseModel):
    data: date | None = None
    inicio: date | None = None
    status: Literal["vigente", "vencendo", "vencido", "indeterminado", "sem_validade"] = "sem_validade"
    dias_restantes: int | None = None        # negativo = vencido há N dias
    origem: Literal["texto", "modelo", "regra"] | None = None
    evidencia: str | None = None             # trecho do documento que comprova a data


class TrabalhadorRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    rotulo: str
    cpf_mascarado: str


class DocumentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    codigo: str = ""                         # identificador curto para a tela (DOC-2026-AB12CD)
    lote_id: str
    ordem: int
    tipo: str
    tipo_nome: str = ""
    setor: str = ""
    titulo: str | None = None
    validade: ValidadeOut = Field(default_factory=ValidadeOut)
    trabalhador: TrabalhadorRef | None = None    # dono do documento (pela impressão digital do CPF)
    criado_em: datetime | None = None
    pagina_inicio: int
    pagina_fim: int
    n_paginas: int = 0
    confianca: float
    status_revisao: str
    motivos: list[str] | None
    prioridade: str = "media"
    prioridade_motivo: str | None = None
    resumo: str | None = None
    resumo_origem: str | None = None
    campos: dict | None = None

    _p = field_validator("prioridade", mode="before")(_prioridade_texto)


class PaginaDocumentos(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    paginas: int
    itens: list[DocumentoOut]


class RevisaoIn(BaseModel):
    acao: Literal["aprovar", "alterar_tipo", "dividir", "juntar_proximo", "alterar_prioridade"]
    usuario: str | None = Field(default=None, max_length=100)   # com login ativo vem do token
    tipo: str | None = None              # para alterar_tipo
    pagina_corte: int | None = None      # para dividir: nº (0-based) da 1ª página do novo documento
    prioridade: Prioridade | None = None  # para alterar_prioridade


class RevisaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    documento_id: str | None
    lote_id: str
    usuario: str
    acao: str
    antes: dict | None
    depois: dict | None
    em: datetime


class BuscaItem(BaseModel):
    documento_id: str
    lote_id: str
    tipo: str
    trecho: str


# ------------------------------------------------------------ login e usuários
class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    perfil: str


class UsuarioIn(BaseModel):
    login: str = Field(min_length=3, max_length=100)
    nome: str = Field(min_length=1, max_length=200)
    senha: str = Field(min_length=8, max_length=200)
    perfil: Literal["analista", "revisor", "admin"]


class CadastroIn(BaseModel):
    login: str = Field(min_length=3, max_length=100)
    nome: str = Field(min_length=1, max_length=200)
    senha: str = Field(min_length=8, max_length=200)

    @field_validator("login", "nome")
    @classmethod
    def remover_espacos(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("O campo não pode ficar vazio")
        return valor


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    login: str
    nome: str
    perfil: str
    ativo: bool


class EuOut(BaseModel):
    login: str
    perfil: str
    autenticado: bool
