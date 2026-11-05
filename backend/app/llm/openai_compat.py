"""Cliente para qualquer API compatível com o formato OpenAI /chat/completions.

Cobre com o MESMO código: OpenAI, Gemini (endpoint OpenAI-compatível), DeepSeek,
Ollama local (Qwen-VL, Gemma 3, Llama Vision...), Groq, OpenRouter, LM Studio, vLLM.
"""
import base64
import io
import json
import logging
import re

import httpx
from PIL import Image

from app.llm.base import RespostaLLM
from app.tipos import DESCONHECIDO, TIPOS

log = logging.getLogger(__name__)

URLS_PADRAO = {
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "deepseek": "https://api.deepseek.com/v1",
    "ollama": "http://localhost:11434/v1",
}

PROMPT_SISTEMA = """Você classifica páginas de documentos digitalizados que chegaram em um lote.
Tipos possíveis (use o CÓDIGO):
{tipos}
- {desconhecido}: nenhum dos anteriores

Responda SOMENTE com JSON válido, sem texto fora dele:
{{"tipo": "<CODIGO>", "inicio_documento": true|false, "confianca": <0 a 1>, "justificativa": "<até 20 palavras>"}}

"inicio_documento" = true se esta página é a PRIMEIRA página de um novo documento,
false se ela continua o documento da página anterior.
Dados pessoais foram mascarados como [CPF], [RG] etc. — isso é esperado."""


def _imagem_para_data_url(png: bytes, lado_max: int = 1600) -> str:
    """Reduz e converte p/ JPEG: corta custo de tokens sem perder legibilidade."""
    img = Image.open(io.BytesIO(png)).convert("L")
    img.thumbnail((lado_max, lado_max))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _extrair_json(conteudo: str) -> dict:
    conteudo = re.sub(r"^```(json)?|```$", "", conteudo.strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", conteudo, re.S)
    return json.loads(m.group(0) if m else conteudo)


class ClienteOpenAICompat:
    def __init__(self, base_url: str, modelo: str, api_key: str | None, multimodal: bool, timeout: int):
        self.base_url = base_url.rstrip("/")
        self.modelo = modelo
        self.multimodal = multimodal
        self.http = httpx.Client(timeout=timeout, headers={"Authorization": f"Bearer {api_key or 'none'}"})
        tipos = "\n".join(f"- {c}: {t['nome']}" for c, t in TIPOS.items())
        self.sistema = PROMPT_SISTEMA.format(tipos=tipos, desconhecido=DESCONHECIDO)

    def classificar(self, texto, imagem_png, contexto_anterior):
        conteudo_usuario: list[dict] = [{
            "type": "text",
            "text": (f"PÁGINA ANTERIOR: {contexto_anterior or '(esta é a primeira página do lote)'}\n\n"
                     f"TEXTO OCR DESTA PÁGINA:\n{(texto or '')[:6000]}"),
        }]
        if self.multimodal and imagem_png:
            conteudo_usuario.append({"type": "image_url", "image_url": {"url": _imagem_para_data_url(imagem_png)}})

        corpo = {
            "model": self.modelo,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": self.sistema},
                         {"role": "user", "content": conteudo_usuario}],
        }
        try:
            r = self.http.post(f"{self.base_url}/chat/completions", json=corpo)
            r.raise_for_status()
            dados = _extrair_json(r.json()["choices"][0]["message"]["content"])
        except Exception as e:  # rede, cota, JSON inválido... nunca derruba o pipeline
            log.warning("modelo falhou: %s", e)
            return None

        tipo = str(dados.get("tipo", DESCONHECIDO)).upper()
        if tipo not in TIPOS:
            tipo = DESCONHECIDO
        try:
            conf = max(0.0, min(1.0, float(dados.get("confianca", 0.5))))
        except (TypeError, ValueError):
            conf = 0.5
        inicio = dados.get("inicio_documento")
        return RespostaLLM(tipo=tipo, inicio_documento=inicio if isinstance(inicio, bool) else None,
                           confianca=conf, justificativa=str(dados.get("justificativa", ""))[:300])
