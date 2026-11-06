import logging
from functools import lru_cache

from app.config import settings
from app.llm.base import ClassificadorLLM, RespostaLLM  # noqa: F401

log = logging.getLogger(__name__)
_erro_configuracao: str | None = None


@lru_cache
def obter_llm() -> ClassificadorLLM | None:
    """Fábrica: devolve o cliente configurado, ou None se LLM_PROVIDER=nenhum.

    Configuração inválida NUNCA derruba o processamento: registra o erro uma vez (log e /health)
    e o pipeline segue só com as regras."""
    global _erro_configuracao
    prov = settings.LLM_PROVIDER.lower()
    if prov in ("", "nenhum", "none"):
        _erro_configuracao = None
        return None
    from app.llm.openai_compat import URLS_PADRAO, ClienteOpenAICompat
    base = settings.LLM_BASE_URL or URLS_PADRAO.get(prov)
    if not base or not settings.LLM_MODEL:
        _erro_configuracao = (f"modelo '{prov}' precisa de LLM_MODEL e LLM_BASE_URL (ou um provedor conhecido); "
                              "seguindo só com as regras")
        log.error(_erro_configuracao)
        return None
    _erro_configuracao = None
    # DeepSeek pela API oficial só recebe texto
    multimodal = settings.LLM_MULTIMODAL and prov != "deepseek"
    return ClienteOpenAICompat(base, settings.LLM_MODEL, settings.LLM_API_KEY, multimodal, settings.LLM_TIMEOUT,
                               chars_por_parte=settings.RESUMO_CHARS_POR_PARTE)


def erro_configuracao() -> str | None:
    obter_llm()
    return _erro_configuracao
