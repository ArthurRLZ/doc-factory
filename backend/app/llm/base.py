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


class ClassificadorLLM(Protocol):
    def classificar(self, texto: str, imagem_png: bytes | None, contexto_anterior: str | None,
                    exemplos: list[tuple[str, str]] | None = None) -> RespostaLLM | None:
        """Retorna None em caso de falha (o pipeline segue só com as regras)."""
        ...

    def resumir(self, tipo_nome: str, campos: list[str], texto: str) -> RespostaResumo | None:
        """Resume um documento inteiro (texto já anonimizado). None em caso de falha."""
        ...
