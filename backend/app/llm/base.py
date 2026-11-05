"""Interface única de modelo — trocar de provedor = trocar variável de ambiente."""
from dataclasses import dataclass
from typing import Protocol


@dataclass
class RespostaLLM:
    tipo: str
    inicio_documento: bool | None
    confianca: float
    justificativa: str = ""


class ClassificadorLLM(Protocol):
    def classificar(self, texto: str, imagem_png: bytes | None, contexto_anterior: str | None) -> RespostaLLM | None:
        """Retorna None em caso de falha (o pipeline segue só com as regras)."""
        ...
