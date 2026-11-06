"""Canais de envio dos alertas: e-mail (SMTP), WhatsApp (Evolution API) e simulado (só loga).

Por que um modo simulado: para demonstrar e testar sem mandar nada de verdade. Segredos (senha SMTP, apikey da
Evolution) nunca entram em log nem na mensagem de erro.
"""
import logging
import smtplib
from email.message import EmailMessage
from typing import Protocol

import httpx

from app.config import settings

log = logging.getLogger(__name__)


class ErroEnvio(Exception):
    """Falha ao enviar (sem expor segredos)."""


class Canal(Protocol):
    nome: str

    def enviar(self, destino: str, assunto: str, texto: str) -> None:
        """Envia ou levanta ErroEnvio."""
        ...


def email_configurado() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_REMETENTE)


def whatsapp_configurado() -> bool:
    return bool(settings.EVOLUTION_URL and settings.EVOLUTION_INSTANCIA and settings.EVOLUTION_APIKEY)


class CanalEmail:
    nome = "email"

    def enviar(self, destino: str, assunto: str, texto: str) -> None:
        msg = EmailMessage()
        msg["Subject"], msg["From"], msg["To"] = assunto, settings.SMTP_REMETENTE, destino
        msg.set_content(texto, charset="utf-8")
        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
                if settings.SMTP_TLS:
                    smtp.starttls()
                if settings.SMTP_USUARIO:
                    smtp.login(settings.SMTP_USUARIO, settings.SMTP_SENHA)
                smtp.send_message(msg)
        except Exception as e:
            raise ErroEnvio(f"falha no SMTP ({type(e).__name__})") from None


def _payload(destino: str, texto: str) -> dict:
    """Corpo do POST /message/sendText da Evolution API v2. Na v1 o formato era
    {"number": ..., "options": {...}, "textMessage": {"text": ...}} — se a sua instância for v1, ajuste só aqui."""
    return {"number": destino, "text": texto}


def criar_http() -> httpx.Client:
    """Cliente HTTP do WhatsApp (os testes trocam por um httpx.MockTransport)."""
    return httpx.Client(timeout=15)


class CanalWhatsAppEvolution:
    nome = "whatsapp"

    def __init__(self, http: httpx.Client | None = None):
        self.http = http or criar_http()

    def enviar(self, destino: str, assunto: str, texto: str) -> None:
        url = f"{settings.EVOLUTION_URL.rstrip('/')}/message/sendText/{settings.EVOLUTION_INSTANCIA}"
        try:
            r = self.http.post(url, headers={"apikey": settings.EVOLUTION_APIKEY, "Content-Type": "application/json"},
                               json=_payload(destino, texto))
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ErroEnvio(f"Evolution API respondeu {e.response.status_code}") from None
        except Exception as e:
            raise ErroEnvio(f"falha ao chamar a Evolution API ({type(e).__name__})") from None


class CanalSimulado:
    def __init__(self, nome: str):
        self.nome = nome

    def enviar(self, destino: str, assunto: str, texto: str) -> None:
        log.info("[ALERTA SIMULADO] %s → %s: %s", self.nome, destino, texto[:200])


def obter_canal(nome: str, simular: bool | None = None) -> Canal:
    """Simulado se ALERTAS_MODO=simulado (ou simular=True); senão o canal real, que precisa estar configurado."""
    if simular or (simular is None and settings.ALERTAS_MODO != "real"):
        return CanalSimulado(nome)
    if nome == "email":
        if not email_configurado():
            raise ErroEnvio("canal não configurado")
        return CanalEmail()
    if nome == "whatsapp":
        if not whatsapp_configurado():
            raise ErroEnvio("canal não configurado")
        return CanalWhatsAppEvolution()
    raise ErroEnvio(f"canal desconhecido: {nome}")
