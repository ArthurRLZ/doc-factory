"""Anonimização (LGPD): mascara dados pessoais no texto, na imagem e no PDF.

Fluxo de privacidade:
  OCR → detecta dados pessoais → texto mascarado vai pro banco, pra busca e pro modelo
                               → imagem enviada ao modelo vai com tarja
                               → PDF anonimizado usa redaction real do PyMuPDF

O que é detectado:
  - CPF, CNPJ, RG, e-mail, telefone ............ padrões fixos (regex)
  - NOMES de pessoas ............................ 1) rótulos do documento ("Nome:", "Cliente:",
                                                     "Contratante:", "filho de"...) e
                                                  2) reconhecedor de entidades spaCy (pt) no texto corrido
                                                  Empresas (LTDA, S.A....) e cidades continuam visíveis.
  - ENDEREÇO (logradouro + número) e CEP ........ regex ("Rua", "Av.", "Travessa"... + número)
"""
import io
import logging
import re
import threading
from functools import lru_cache

from PIL import Image, ImageDraw

from app.config import settings

log = logging.getLogger(__name__)

# ------------------------------------------------------------------ padrões fixos
PADROES: dict[str, re.Pattern] = {
    "CNPJ": re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"),
    "CPF": re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\b\d{11}\b"),
    "RG": re.compile(r"\b\d{1,2}\.\d{3}\.\d{3}-?[\dXx]\b"),
    "EMAIL": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "TELEFONE": re.compile(r"\(?\b\d{2}\)?\s?9?\d{4}-\d{4}\b"),
}

RX_CEP = re.compile(r"\b\d{5}-\d{3}\b|(?i:\bcep)[:\s]*\d{8}\b")
RX_ENDERECO = re.compile(
    r"(?i:\b(?:rua|r\.|avenida|av\.?|travessa|tv\.|alameda|al\.|rodovia|estrada|pra[çc]a|largo|"
    r"loteamento|s[íi]tio|vila)\s)"
    r"[^,\n\[\]]{2,60}?"                                    # nome do logradouro
    r"(?:,?\s*(?i:n[º°o]\.?\s*)?\d{1,5}[A-Za-z]?\b)"        # número
)

# ------------------------------------------------------------------ nomes por rótulo
_PALAVRA_NOME = r"[A-ZÀ-Ý][a-zà-ÿ]+|[A-ZÀ-Ý]{2,}"
_CONECTOR = r"(?:da|de|do|das|dos|DA|DE|DO|DAS|DOS)"
_NOME = rf"(?:{_PALAVRA_NOME})(?:[ \t]{{1,2}}(?:{_CONECTOR}[ \t]{{1,2}})?(?:{_PALAVRA_NOME}))*"
_SEPARADOR_NOMES = r"[ \t]*(?:/|,|\be\b|\bE\b)[ \t]*"
# rótulos seguidos de ":" ou "-" (formulários) ...
_ROTULOS_DOIS_PONTOS = (r"nome(?:\s+completo)?|cliente|contratante|contratad[oa]|locador[a]?|locat[aá]ri[oa]|"
                        r"destinat[aá]ri[oa]|titular|filia[cç][aã]o|pai|m[aã]e|requerente|requerid[oa]|"
                        r"outorgante|outorgad[oa]|propriet[aá]ri[oa]|respons[aá]vel|paciente|alun[oa]|"
                        r"benefici[aá]ri[oa]|segurad[oa]|declarante|interessad[oa]|testemunhas?|assinado\s+por")
# ... e expressões do texto corrido
_ROTULOS_TEXTO = r"filh[oa]\s+de|nascimento\s+de|casamento\s+de|[óo]bito\s+de|neto\s+de|neta\s+de"
RX_NOME_ROTULO = re.compile(
    rf"(?:(?i:\b(?:{_ROTULOS_DOIS_PONTOS}))[ \t]*[:\-][ \t]*|(?i:\b(?:{_ROTULOS_TEXTO}))[ \t]+)"
    rf"(?P<nomes>{_NOME}(?:{_SEPARADOR_NOMES}{_NOME})*)"
)
# palavras que nunca fazem parte de um nome (rótulos, siglas, marcadores)
_NAO_NOME = {
    "CPF", "CNPJ", "RG", "CEP", "UF", "PE", "LTDA", "ME", "EPP", "EIRELI", "SA", "S.A", "CONTRATANTE",
    "CONTRATADA", "CONTRATADO", "LOCADOR", "LOCATÁRIO", "LOCATARIA", "LOCATÁRIA", "NOME", "FILIAÇÃO",
    "NATURALIDADE", "DATA", "ENDEREÇO", "CLIENTE", "DESTINATÁRIO", "EMITENTE", "TESTEMUNHAS", "ASSINATURA",
    "NASCIMENTO", "REGISTRO", "GERAL", "ÓRGÃO", "EXPEDIDOR", "CLÁUSULA",
}
# o trecho é de EMPRESA, não de pessoa: fica visível
_RX_EMPRESA = re.compile(r"(?i)\b(ltda|s\.?/?a\.?|eireli|me|epp|empresa|companhia|cia|banco|distribuidora|"
                         r"cooperativa|associa[cç][aã]o|instituto|prefeitura|secretaria|minist[eé]rio|"
                         r"cart[oó]rio|universidade|faculdade|escola|hospital|igreja|condom[ií]nio)\b")


def _nomes_por_rotulo(texto: str) -> list[tuple[int, int]]:
    spans = []
    for m in RX_NOME_ROTULO.finditer(texto):
        ini, fim = m.span("nomes")
        trecho = texto[ini:fim]
        if _RX_EMPRESA.search(trecho):
            continue
        # corta no primeiro token que não pode ser nome (ex.: "Maria Silva CPF" → "Maria Silva")
        pos = ini
        for tok in re.finditer(r"\S+", trecho):
            if tok.group().strip(",.;:/").upper() in _NAO_NOME:
                fim = ini + tok.start()
                break
        trecho = texto[pos:fim].rstrip(" \t,/")
        if len(trecho.strip()) >= 2:
            spans.append((pos, pos + len(trecho)))
    return spans


# ------------------------------------------------------------------ nomes pelo spaCy
_lock = threading.Lock()


@lru_cache(maxsize=1)
def _nlp():
    try:
        import spacy
        return spacy.load(settings.NER_MODELO, disable=["parser", "lemmatizer", "attribute_ruler"])
    except Exception as e:  # spaCy ou modelo ausente: segue só com as regras por rótulo
        log.warning("reconhecedor de nomes indisponível (%s); usando só regras por rótulo", e)
        return None


def _nomes_por_ner(texto: str) -> list[tuple[int, int]]:
    nlp = _nlp()
    if nlp is None or not texto.strip():
        return []
    with _lock:
        doc = nlp(texto[:100_000])
    spans = []
    for ent in doc.ents:
        if ent.label_ != "PER":
            continue
        # um nome nunca atravessa linha: corta na primeira quebra
        toks = []
        for t in ent:
            if "\n" in t.text or "\n" in t.whitespace_ and toks:
                if "\n" not in t.text:
                    toks.append(t)
                break
            toks.append(t)
        # tira tokens que não são nome (ex.: "Maria Silva   CPF") e espaços/pontuação
        toks = [t for t in toks if t.text.strip(",.;:/").upper() not in _NAO_NOME
                and not t.is_punct and not t.is_space]
        if not toks or _RX_EMPRESA.search(ent.text):
            continue
        if not any(re.fullmatch(_PALAVRA_NOME, t.text) for t in toks):
            continue
        spans.append((toks[0].idx, toks[-1].idx + len(toks[-1].text)))
    return spans


# ------------------------------------------------------------------ juntando tudo
def encontrar_sensiveis(texto: str) -> list[tuple[int, int, str]]:
    """Todos os trechos sensíveis do texto: [(início, fim, rótulo)], sem sobreposição."""
    texto = texto or ""
    achados: list[tuple[int, int, str]] = []
    for rotulo, rx in PADROES.items():
        achados += [(m.start(), m.end(), rotulo) for m in rx.finditer(texto)]
    if settings.ANONIMIZAR_ENDERECOS:
        achados += [(m.start(), m.end(), "ENDERECO") for m in RX_ENDERECO.finditer(texto)]
        achados += [(m.start(), m.end(), "CEP") for m in RX_CEP.finditer(texto)]
    if settings.ANONIMIZAR_NOMES:
        achados += [(a, b, "NOME") for a, b in _nomes_por_rotulo(texto) + _nomes_por_ner(texto)]
    # sem sobreposição: o que começa antes ganha; no empate, o mais longo
    achados.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    final, fim_atual = [], -1
    for ini, fim, rot in achados:
        if ini >= fim_atual and fim > ini:
            final.append((ini, fim, rot))
            fim_atual = fim
    return final


def mascarar_texto(texto: str) -> tuple[str, dict[str, int]]:
    texto = texto or ""
    contagem: dict[str, int] = {}
    partes, pos = [], 0
    for ini, fim, rot in encontrar_sensiveis(texto):
        partes += [texto[pos:ini], f"[{rot}]"]
        pos = fim
        contagem[rot] = contagem.get(rot, 0) + 1
    partes.append(texto[pos:])
    return "".join(partes), contagem


def indices_sensiveis(palavras: list[dict]) -> set[int]:
    """Quais palavras (por índice) fazem parte de um dado sensível.
    Remonta o texto (quebra de linha quando muda a linha do OCR), procura os trechos e mapeia
    de volta pelas posições — assim nome e endereço também viram tarja na imagem e no PDF."""
    if not palavras:
        return set()
    offsets, partes, pos, linha_ant = [], [], 0, None
    for w in palavras:
        linha = (w.get("b"), w.get("l"))
        sep = "" if not partes else ("\n" if linha != linha_ant else " ")
        pos += len(sep)
        partes.append(sep + w["t"])
        offsets.append((pos, pos + len(w["t"])))
        pos += len(w["t"])
        linha_ant = linha
    texto = "".join(partes)
    alvo = set()
    for ini, fim, _rot in encontrar_sensiveis(texto):
        for i, (a, b) in enumerate(offsets):
            if a < fim and b > ini:
                alvo.add(i)
    return alvo


def tarjar_imagem(png: bytes, palavras: list[dict], indices: set[int], dpi: int, margem_px: int = 4) -> bytes:
    """Pinta caixas pretas sobre os dados sensíveis (usado antes de mandar a imagem para o modelo)."""
    if not indices:
        return png
    img = Image.open(io.BytesIO(png)).convert("L")
    draw = ImageDraw.Draw(img)
    k = dpi / 72.0
    for i in indices:
        w = palavras[i]
        draw.rectangle([w["x0"] * k - margem_px, w["y0"] * k - margem_px,
                        w["x1"] * k + margem_px, w["y1"] * k + margem_px], fill=0)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()
