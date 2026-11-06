"""Utilitários usados em vários lugares (um lugar só para cada regra)."""
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

from app.config import settings


def fuso() -> timezone:
    return timezone(timedelta(hours=settings.FUSO_HORAS))


def agora_local() -> datetime:
    return datetime.now(fuso())


def hoje() -> date:
    """O "hoje" do negócio (fuso FUSO_HORAS), igual em validade, painel e filtros.
    Não usar date.today(): no Docker o relógio do servidor é UTC e vira o dia às 21h de Brasília."""
    return agora_local().date()


def content_disposition(nome: str, inline: bool = False) -> str:
    """Cabeçalho de download seguro para QUALQUER nome (acentos, aspas, emoji): ASCII de reserva +
    filename* em UTF-8 (RFC 6266/5987). Sem isso, nomes fora do latin-1 derrubam a resposta com erro 500."""
    ascii_ = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    ascii_ = re.sub(r'[^A-Za-z0-9._ -]', "_", ascii_).strip() or "arquivo"
    tipo = "inline" if inline else "attachment"
    return f"{tipo}; filename=\"{ascii_}\"; filename*=UTF-8''{quote(nome, safe='')}"
