"""Interface única de modelo — trocar de provedor = trocar variável de ambiente."""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class RespostaLLM:
    tipo: str
    inicio_documento: bool | None
    confianca: float
    justificativa: str = ""


@dataclass
class RespostaResumo:
    resumo: str
    campos: dict = field(default_factory=dict)
    prioridade: str | None = None          # alta | media | baixa (sugestão do modelo)
    motivo_prioridade: str = ""
    partes: int = 1                        # em quantas partes o documento foi resumido
    validade: dict | None = None           # {"data", "inicio", "evidencia"} — conferido em pipeline/validade.py


@dataclass
class RespostaRegras:
    regras: list[dict] = field(default_factory=list)


class ClassificadorLLM(Protocol):
    """Métodos além de classificar/resumir são OPCIONAIS: quem chama usa getattr(llm, "nome", None)
    e cai no fallback por regras se o cliente não tiver o método."""

    def classificar(self, texto: str, imagem_png: bytes | None, contexto_anterior: str | None,
                    exemplos: list[tuple[str, str]] | None = None) -> RespostaLLM | None:
        """Retorna None em caso de falha (o pipeline segue só com as regras)."""
        ...

    def resumir(self, tipo_nome: str, campos: list[str], texto: str) -> RespostaResumo | None:
        """Resume um documento inteiro (texto já anonimizado). None em caso de falha."""
        ...

    def interpretar_regras_separacao(self, texto: str, tipos: dict[str, str]) -> list[dict] | None:
        """(opcional) Frase em português → regras de separação; None em falha."""
        ...

    def extrair_funcao(self, texto: str, funcoes: dict[str, str]) -> dict | None:
        """(opcional) {"funcao", "chave", "evidencia"} do documento trabalhista; None em falha."""
        ...
