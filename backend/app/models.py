"""Modelo de dados.

Regra de ouro: o banco guarda METADADOS. Imagens, PDFs e caixas de palavras
ficam no storage (disco/MinIO/S3) e o banco guarda só a chave (key) + hash.
"""
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    DDL,
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.status import StatusLote, StatusPagina


def agora():
    return datetime.now(timezone.utc)


def novo_id():
    return uuid.uuid4().hex


class Lote(Base):
    """Um arquivo enviado (PDF/TIFF com centenas de páginas)."""
    __tablename__ = "lotes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=novo_id)
    nome: Mapped[str] = mapped_column(String(255))
    arquivo_key: Mapped[str] = mapped_column(String(512))          # chave no storage
    hash_sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    mime: Mapped[str] = mapped_column(String(100))
    tamanho_bytes: Mapped[int] = mapped_column(Integer)
    total_paginas: Mapped[int] = mapped_column(Integer, default=0)
    # recebido → processando → segmentando → concluido | erro
    status: Mapped[str] = mapped_column(String(20), default=StatusLote.RECEBIDO, index=True)
    erro: Mapped[str | None] = mapped_column(Text)
    # 1 baixa · 2 normal · 3 alta — o worker atende primeiro os lotes de prioridade maior
    prioridade: Mapped[int] = mapped_column(Integer, default=2, server_default="2", index=True)
    alertas: Mapped[list | None] = mapped_column(JSON)               # sinais de fraude do ARQUIVO (metadados)
    enviado_por: Mapped[str | None] = mapped_column(String(100))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, onupdate=agora)

    # uso de IA na ÚLTIMA execução (incremento atômico em app/llm/contador.py; reprocessar zera)
    llm_chamadas_classificacao: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    llm_chamadas_resumo: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    llm_chamadas_outras: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    llm_paginas: Mapped[int] = mapped_column(Integer, default=0, server_default="0")   # páginas que consultaram a IA

    paginas: Mapped[list["Pagina"]] = relationship(back_populates="lote", cascade="all, delete-orphan",
                                                   order_by="Pagina.numero")
    documentos: Mapped[list["Documento"]] = relationship(back_populates="lote", cascade="all, delete-orphan",
                                                         order_by="Documento.ordem")

    @property
    def ia(self) -> dict:
        """Quanto este lote dependeu da IA ("só 3 de 14 páginas usaram IA")."""
        from app.config import settings
        cl, rs, ou = (self.llm_chamadas_classificacao or 0), (self.llm_chamadas_resumo or 0), (self.llm_chamadas_outras or 0)
        total = cl + rs + ou
        pags = self.llm_paginas or 0
        return {"chamadas_total": total, "chamadas_classificacao": cl, "chamadas_resumo": rs, "chamadas_outras": ou,
                "paginas_com_ia": pags, "paginas_total": self.total_paginas or 0,
                "percentual_paginas_com_ia": round(100 * pags / max(self.total_paginas or 0, 1), 1),
                "custo_estimado_brl": round(total * settings.LLM_CUSTO_POR_CHAMADA_BRL, 4)}


class VersaoLote(Base):
    """Retrato anterior ao reprocessamento; inclui documentos, páginas e revisões."""
    __tablename__ = "versoes_lote"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lote_id: Mapped[str] = mapped_column(ForeignKey("lotes.id", ondelete="CASCADE"), index=True)
    usuario: Mapped[str] = mapped_column(String(100))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    dados: Mapped[dict] = mapped_column(JSON)


class Pagina(Base):
    """Unidade de trabalho do worker. Cada página é processada de forma idempotente."""
    __tablename__ = "paginas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lote_id: Mapped[str] = mapped_column(ForeignKey("lotes.id", ondelete="CASCADE"), index=True)
    numero: Mapped[int] = mapped_column(Integer)                     # 0-based dentro do lote
    documento_id: Mapped[str | None] = mapped_column(ForeignKey("documentos.id", ondelete="SET NULL"), index=True)

    # pendente → processando → ok | erro (retenta) → falhou (desistiu)
    status: Mapped[str] = mapped_column(String(20), default=StatusPagina.PENDENTE, index=True)
    tentativas: Mapped[int] = mapped_column(Integer, default=0)
    erro: Mapped[str | None] = mapped_column(Text)

    # artefatos no storage
    imagem_key: Mapped[str | None] = mapped_column(String(512))       # PNG 300 dpi (para OCR)
    thumb_key: Mapped[str | None] = mapped_column(String(512))        # JPG pequeno (front)
    palavras_key: Mapped[str | None] = mapped_column(String(512))     # JSON com caixas das palavras
    largura_pt: Mapped[float | None] = mapped_column(Float)
    altura_pt: Mapped[float | None] = mapped_column(Float)

    # OCR
    nativa: Mapped[bool] = mapped_column(Boolean, default=False)     # PDF digital (sem OCR)
    texto: Mapped[str | None] = mapped_column(Text)                  # texto já ANONIMIZADO
    ocr_confianca: Mapped[float | None] = mapped_column(Float)       # 0-100 (Tesseract)
    em_branco: Mapped[bool] = mapped_column(Boolean, default=False)

    # classificação
    tipo_regra: Mapped[str | None] = mapped_column(String(50))
    conf_regra: Mapped[float | None] = mapped_column(Float)
    tipo_llm: Mapped[str | None] = mapped_column(String(50))
    conf_llm: Mapped[float | None] = mapped_column(Float)
    inicio_llm: Mapped[bool | None] = mapped_column(Boolean)
    tipo: Mapped[str | None] = mapped_column(String(50))             # decisão combinada
    confianca: Mapped[float | None] = mapped_column(Float)
    divergente: Mapped[bool] = mapped_column(Boolean, default=False)
    sinais: Mapped[dict | None] = mapped_column(JSON)                # pagina_x, pagina_n, titulo_topo...
    llm_chamado: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")   # IA consultada p/ classificar

    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, onupdate=agora)

    lote: Mapped[Lote] = relationship(back_populates="paginas")

    __table_args__ = (Index("ix_paginas_lote_numero", "lote_id", "numero", unique=True),)


class Documento(Base):
    """Documento lógico detectado dentro do lote (intervalo de páginas)."""
    __tablename__ = "documentos"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=novo_id)
    lote_id: Mapped[str] = mapped_column(ForeignKey("lotes.id", ondelete="CASCADE"), index=True)
    ordem: Mapped[int] = mapped_column(Integer)
    tipo: Mapped[str] = mapped_column(String(50), index=True)
    pagina_inicio: Mapped[int] = mapped_column(Integer)
    pagina_fim: Mapped[int] = mapped_column(Integer)
    confianca: Mapped[float] = mapped_column(Float)
    # auto_aprovado | pendente | revisado
    status_revisao: Mapped[str] = mapped_column(String(20), index=True)
    motivos: Mapped[list | None] = mapped_column(JSON)
    texto: Mapped[str | None] = mapped_column(Text)                  # texto anonimizado (busca)
    pdf_key: Mapped[str | None] = mapped_column(String(512))         # PDF pesquisável
    pdf_anon_key: Mapped[str | None] = mapped_column(String(512))    # PDF com tarjas reais

    # resumo (feito só com o texto já anonimizado)
    resumo: Mapped[str | None] = mapped_column(Text)
    campos: Mapped[dict | None] = mapped_column(JSON)                # campos-chave extraídos por tipo
    resumo_origem: Mapped[str | None] = mapped_column(String(20))    # modelo | simples
    # prioridade na fila de revisão: 1 baixa · 2 média · 3 alta
    prioridade: Mapped[int] = mapped_column(Integer, default=2, server_default="2", index=True)
    prioridade_motivo: Mapped[str | None] = mapped_column(String(300))
    prioridade_manual: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")  # revisor decidiu
    titulo: Mapped[str | None] = mapped_column(String(200))           # título lido no documento (p/ a tela)
    trabalhador_id: Mapped[int | None] = mapped_column(ForeignKey("trabalhadores.id", ondelete="SET NULL"), index=True)
    # sinais de fraude: confiavel | atencao | alto_risco, com a lista de alertas (código, gravidade, evidência)
    risco: Mapped[str] = mapped_column(String(20), default="confiavel", server_default="confiavel", index=True)
    alertas: Mapped[list | None] = mapped_column(JSON)
    texto_hash: Mapped[str | None] = mapped_column(String(64), index=True)   # detecta documento repetido

    # validade / vigência (o status — vigente, vencendo, vencido — é calculado na leitura, com a data de hoje)
    validade_data: Mapped[date | None] = mapped_column(Date, index=True)
    validade_inicio: Mapped[date | None] = mapped_column(Date)
    validade_origem: Mapped[str | None] = mapped_column(String(20))   # texto | modelo | regra
    validade_evidencia: Mapped[str | None] = mapped_column(String(500))
    # quem decidiu o tipo: regra | ia | combinado | humano (app/pipeline/explicabilidade.py)
    decidido_por: Mapped[str | None] = mapped_column(String(12))
    ia_justificativa: Mapped[str | None] = mapped_column(String(500))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    lote: Mapped[Lote] = relationship(back_populates="documentos")
    revisoes: Mapped[list["Revisao"]] = relationship(back_populates="documento", cascade="all, delete-orphan")
    trabalhador: Mapped["Trabalhador | None"] = relationship(back_populates="documentos")


class Trabalhador(Base):
    """Pessoa a quem os documentos pertencem — identificada pela impressão digital do CPF (nunca o CPF)."""
    __tablename__ = "trabalhadores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cpf_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    cpf_mascarado: Mapped[str] = mapped_column(String(20))           # ***.982.247-**
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    documentos: Mapped[list[Documento]] = relationship(back_populates="trabalhador")

    @property
    def rotulo(self) -> str:
        return f"Trabalhador {self.cpf_mascarado}"


# Busca full-text em português com índice GIN (só no PostgreSQL; no SQLite cai para LIKE)
event.listen(Documento.__table__, "after_create", DDL(
    "CREATE INDEX IF NOT EXISTS ix_documentos_fts ON documentos "
    "USING gin (to_tsvector('portuguese', coalesce(texto, '')))"
).execute_if(dialect="postgresql"))


class Revisao(Base):
    """Trilha de auditoria de cada decisão humana (vira dado de treino depois)."""
    __tablename__ = "revisoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    documento_id: Mapped[str | None] = mapped_column(ForeignKey("documentos.id", ondelete="SET NULL"), index=True)
    lote_id: Mapped[str] = mapped_column(String(32), index=True)
    usuario: Mapped[str] = mapped_column(String(100))
    acao: Mapped[str] = mapped_column(String(30))     # aprovar | alterar_tipo | dividir | juntar_proximo
    antes: Mapped[dict | None] = mapped_column(JSON)
    depois: Mapped[dict | None] = mapped_column(JSON)
    em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    documento: Mapped[Documento | None] = relationship(back_populates="revisoes")


class Aprendizado(Base):
    """O que o sistema aprendeu com uma correção humana de tipo (vira regra e exemplo para o modelo)."""
    __tablename__ = "aprendizados"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    titulo: Mapped[str] = mapped_column(String(200), index=True)      # título normalizado (sem acento, minúsculo)
    tipo_errado: Mapped[str | None] = mapped_column(String(50))
    tipo_certo: Mapped[str] = mapped_column(String(50))
    exemplo: Mapped[str | None] = mapped_column(Text)                # trecho do texto JÁ anonimizado
    documento_id: Mapped[str | None] = mapped_column(String(32))
    usuario: Mapped[str] = mapped_column(String(100))
    usos: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class Configuracao(Base):
    """Ajustes feitos em tempo de execução (ex.: limiar de revisão), valem para API e workers."""
    __tablename__ = "configuracoes"

    chave: Mapped[str] = mapped_column(String(100), primary_key=True)
    valor: Mapped[str] = mapped_column(String(500))
    alterado_por: Mapped[str | None] = mapped_column(String(100))
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, onupdate=agora)


class Usuario(Base):
    """Login com perfis: analista (envia e consulta) < revisor (revisa) < admin (gerencia usuários)."""
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    login: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(200))
    senha_hash: Mapped[str] = mapped_column(String(300))
    perfil: Mapped[str] = mapped_column(String(20))       # analista | revisor | admin
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
