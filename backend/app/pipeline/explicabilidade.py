"""Quem decidiu o tipo do documento: regra, IA, as duas juntas ou um revisor.

Para a tela mostrar "Decidido pela IA: <justificativa>" sem chamar o modelo de novo: tudo vem do que
o processamento das páginas já gravou (tipo_regra, tipo_llm e sinais["llm_justificativa"]).
"""
from app.models import Pagina

TEXTOS = {"regra": "Decidido por regras", "ia": "Decidido pela IA", "combinado": "Regras e IA concordaram",
          "humano": "Corrigido por revisor"}


def decidido_por(paginas: list[Pagina], tipo_final: str) -> tuple[str, str | None]:
    """Retorna (decidido_por, justificativa_da_ia)."""
    do_tipo = [p for p in paginas if p.tipo == tipo_final]
    com_ia = [p for p in do_tipo if p.tipo_llm]
    if not com_ia:
        return "regra", None

    def just(p: Pagina) -> str | None:
        j = (p.sinais or {}).get("llm_justificativa")
        return str(j)[:500] if j else None

    for p in com_ia:
        if p.tipo_llm == tipo_final and p.tipo_regra != tipo_final:
            return "ia", just(p)
    return "combinado", next((j for j in map(just, com_ia) if j), None)


def origem_texto(decidido: str | None) -> str | None:
    return TEXTOS.get(decidido) if decidido else None
