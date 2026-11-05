from functools import lru_cache

from app.config import settings
from app.llm.base import ClassificadorLLM, RespostaLLM  # noqa: F401


@lru_cache
def obter_llm() -> ClassificadorLLM | None:
    """Fábrica: devolve o cliente configurado, ou None se LLM_PROVIDER=nenhum."""
    prov = settings.LLM_PROVIDER.lower()
    if prov in ("", "nenhum", "none"):
        return None
    from app.llm.openai_compat import URLS_PADRAO, ClienteOpenAICompat
    base = settings.LLM_BASE_URL or URLS_PADRAO.get(prov)
    if not base or not settings.LLM_MODEL:
        raise RuntimeError(f"Modelo '{prov}' precisa de LLM_MODEL e LLM_BASE_URL (ou um provedor conhecido)")
    # DeepSeek pela API oficial só recebe texto
    multimodal = settings.LLM_MULTIMODAL and prov != "deepseek"
    return ClienteOpenAICompat(base, settings.LLM_MODEL, settings.LLM_API_KEY, multimodal, settings.LLM_TIMEOUT,
                               chars_por_parte=settings.RESUMO_CHARS_POR_PARTE)
