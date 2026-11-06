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

from app.llm.base import RespostaLLM, RespostaResumo
from app.tipos import DESCONHECIDO, PRIORIDADES, TIPOS

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

PROMPT_RESUMO = """Você resume documentos digitalizados em português para um analista.
Use SOMENTE o que está no texto. Nunca invente: campo ausente no texto = null.
Dados pessoais foram mascarados como [CPF], [RG] etc. — mantenha os marcadores, não tente adivinhar.

Responda SOMENTE com JSON válido, sem texto fora dele:
{{"resumo": "<2 a 3 frases objetivas>",
  "campos": {{{campos}}},
  "prioridade": "alta" | "media" | "baixa",
  "motivo_prioridade": "<até 15 palavras>",
  "validade": {{"data": "dd/mm/aaaa" | null, "inicio": "dd/mm/aaaa" | null,
               "evidencia": "<trecho COPIADO LITERALMENTE do texto que comprova a data>"}}}}

Prioridade "alta" = exige ação rápida (prazo vencendo, valor alto, pendência, inconsistência);
"baixa" = só arquivar; "media" = o resto.

Validade = até quando o DOCUMENTO vale: "válida até", "validade", vigência de contrato, prazo de certificado.
Se vier como prazo ("vigência de 12 meses a partir de 05/11/2026"), calcule a data final.
NÃO é validade: vencimento de pagamento de guia, boleto ou fatura. Sem validade no texto: "data": null.
A evidência deve ser um trecho que existe no texto, palavra por palavra — ele será conferido."""

PROMPT_PARTE = """Você recebe UMA PARTE de um documento longo em português (texto de OCR, dados pessoais
mascarados). Resuma esta parte em até 6 frases, preservando nomes de empresas, valores, datas,
prazos e obrigações. Use só o que está no texto.
Responda SOMENTE com JSON válido: {"resumo": "<texto>"}"""


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


def dividir_em_partes(texto: str, limite: int) -> list[str]:
    """Quebra o texto em partes de até `limite` caracteres, preferindo cortar entre parágrafos/linhas."""
    texto = (texto or "").strip()
    if len(texto) <= limite:
        return [texto] if texto else []
    partes, atual = [], ""
    for bloco in re.split(r"(\n\s*\n|\n)", texto):
        if len(atual) + len(bloco) <= limite:
            atual += bloco
            continue
        if atual.strip():
            partes.append(atual.strip())
        while len(bloco) > limite:            # bloco gigante sem quebra de linha
            partes.append(bloco[:limite])
            bloco = bloco[limite:]
        atual = bloco
    if atual.strip():
        partes.append(atual.strip())
    return partes


class ClienteOpenAICompat:
    def __init__(self, base_url: str, modelo: str, api_key: str | None, multimodal: bool, timeout: int,
                 chars_por_parte: int = 6000):
        self.base_url = base_url.rstrip("/")
        self.modelo = modelo
        self.multimodal = multimodal
        self.chars_por_parte = chars_por_parte
        self.http = httpx.Client(timeout=timeout, headers={"Authorization": f"Bearer {api_key or 'none'}"})
        # a descrição em linguagem natural de cada tipo é a maior alavanca de precisão do modelo
        tipos = "\n".join(f"- {c}: {t['nome']} — {t.get('descricao', '')}".rstrip(" —") for c, t in TIPOS.items())
        self.sistema = PROMPT_SISTEMA.format(tipos=tipos, desconhecido=DESCONHECIDO)

    def _chat(self, sistema: str, conteudo_usuario) -> dict:
        """Uma chamada /chat/completions que devolve o JSON da resposta. Levanta exceção em falha."""
        corpo = {
            "model": self.modelo,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": sistema},
                         {"role": "user", "content": conteudo_usuario}],
        }
        r = self.http.post(f"{self.base_url}/chat/completions", json=corpo)
        r.raise_for_status()
        return _extrair_json(r.json()["choices"][0]["message"]["content"])

    # ------------------------------------------------------------ resumo
    def resumir(self, tipo_nome: str, campos: list[str], texto: str) -> RespostaResumo | None:
        """Resume o documento inteiro. Documento grande: resume cada parte e depois consolida
        os resumos parciais (repete até caber numa chamada só)."""
        try:
            partes = dividir_em_partes(texto, self.chars_por_parte)
            if not partes:
                return None
            n_partes, rodadas = len(partes), 0
            while len(partes) > 1:
                rodadas += 1
                parciais = [str(self._chat(PROMPT_PARTE, f"PARTE {i + 1} DE {len(partes)}:\n{p}").get("resumo", ""))
                            for i, p in enumerate(partes)]
                juntos = "\n\n".join(f"[Parte {i + 1}] {r}" for i, r in enumerate(parciais) if r.strip())
                partes = dividir_em_partes(juntos, self.chars_por_parte)
                if not partes:
                    return None
                if rodadas >= 5:                      # trava de segurança contra resumos que não encolhem
                    partes = [juntos[:self.chars_por_parte]]
            lista_campos = ", ".join(f'"{c}": "<valor ou null>"' for c in campos)
            dados = self._chat(PROMPT_RESUMO.format(campos=lista_campos),
                               f"TIPO DO DOCUMENTO: {tipo_nome}\n"
                               f"{'RESUMOS DAS PARTES' if n_partes > 1 else 'TEXTO OCR'}:\n{partes[0]}")
        except Exception as e:  # rede, cota, JSON inválido... nunca derruba o pipeline
            log.warning("modelo falhou ao resumir: %s", e)
            return None

        resumo = str(dados.get("resumo") or "").strip()
        if not resumo:
            return None
        brutos = dados.get("campos") if isinstance(dados.get("campos"), dict) else {}
        campos_ok = {c: (None if brutos.get(c) in (None, "", "null") else str(brutos.get(c))[:300]) for c in campos}
        prioridade = str(dados.get("prioridade") or "").lower().replace("é", "e")
        validade = dados.get("validade") if isinstance(dados.get("validade"), dict) else None
        return RespostaResumo(resumo=resumo[:2000], campos=campos_ok,
                              prioridade=prioridade if prioridade in PRIORIDADES else None,
                              motivo_prioridade=str(dados.get("motivo_prioridade") or "")[:200],
                              partes=n_partes, validade=validade)

    # ------------------------------------------------------------ classificação
    def classificar(self, texto, imagem_png, contexto_anterior):
        conteudo_usuario: list[dict] = [{
            "type": "text",
            "text": (f"PÁGINA ANTERIOR: {contexto_anterior or '(esta é a primeira página do lote)'}\n\n"
                     f"TEXTO OCR DESTA PÁGINA:\n{(texto or '')[:6000]}"),
        }]
        if self.multimodal and imagem_png:
            conteudo_usuario.append({"type": "image_url", "image_url": {"url": _imagem_para_data_url(imagem_png)}})

        try:
            dados = self._chat(self.sistema, conteudo_usuario)
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
