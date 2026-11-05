"""Orquestrador do pipeline — liga as etapas e grava no banco/storage.

processar_pagina()       → etapas 1-3, por página, idempotente (pode rodar 2x sem estragar)
finalizar_lote_se_pronto() → quando TODAS as páginas acabaram, roda etapas 4-5 uma única vez
"""
import logging

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.llm import obter_llm
from app.models import Documento, Lote, Pagina, agora
from app.pipeline import rasterizar
from app.pipeline.anonimizar import indices_sensiveis, mascarar_texto, tarjar_imagem
from app.pipeline.classificar import (classificar_por_regras, combinar,
                                      sinais_de_inicio, texto_do_topo)
from app.pipeline.montar import montar_pdf
from app.pipeline.ocr import e_pagina_em_branco, ocr_png
from app.pipeline.segmentar import PaginaInfo, segmentar
from app.storage import get_storage, key_documento, key_pagina
from app.tipos import DESCONHECIDO

log = logging.getLogger(__name__)
STATUS_EM_ABERTO = ("pendente", "processando", "erro")


# ---------------------------------------------------------------- etapas 1-3
def processar_pagina(db: Session, pagina_id: int) -> None:
    st = get_storage()
    p = db.get(Pagina, pagina_id)
    lote = p.lote
    caminho = st.caminho_local(lote.arquivo_key)

    # 1. rasterização (PyMuPDF)
    r = rasterizar.renderizar(caminho, p.numero)

    # 2. OCR (Tesseract) — ou texto nativo se o PDF já for digital
    if r.nativa:
        palavras, texto, ocr_conf, em_branco = r.palavras_nativas, r.texto_nativo, 100.0, False
    else:
        o = ocr_png(r.png)
        palavras, texto, ocr_conf = o.palavras, o.texto, o.confianca
        em_branco = e_pagina_em_branco(len(palavras), o.tinta)

    p.imagem_key = key_pagina(lote.id, p.numero, ".png")
    p.thumb_key = key_pagina(lote.id, p.numero, ".thumb.jpg")
    p.palavras_key = key_pagina(lote.id, p.numero, ".palavras.json")
    st.put_bytes(p.imagem_key, r.png, "image/png")
    st.put_bytes(p.thumb_key, r.thumb_jpg, "image/jpeg")
    st.put_json(p.palavras_key, palavras)

    p.largura_pt, p.altura_pt = r.largura_pt, r.altura_pt
    p.nativa, p.ocr_confianca, p.em_branco = r.nativa, round(ocr_conf, 1), em_branco
    p.texto, _ = mascarar_texto(texto or "")          # banco só guarda texto anonimizado

    # 3. classificação + sinais de início
    if em_branco:
        p.tipo, p.confianca, p.tipo_regra, p.conf_regra, p.sinais = DESCONHECIDO, 0.0, DESCONHECIDO, 0.0, {}
    else:
        topo = texto_do_topo(palavras, r.altura_pt)
        regra = classificar_por_regras(texto or "", topo)
        p.tipo_regra, p.conf_regra = regra.tipo, regra.confianca
        p.sinais = sinais_de_inicio(texto or "", topo) | {"scores": regra.scores}

        llm = obter_llm()
        if llm and (settings.LLM_SEMPRE or regra.confianca < settings.LIMIAR_LLM):
            imagem_segura = tarjar_imagem(r.png, palavras, indices_sensiveis(palavras), settings.DPI_OCR)
            resp = llm.classificar(p.texto, imagem_segura, _contexto_anterior(db, p))
            if resp:
                p.tipo_llm, p.conf_llm, p.inicio_llm = resp.tipo, resp.confianca, resp.inicio_documento
                p.sinais = p.sinais | {"llm_justificativa": resp.justificativa}

        p.tipo, p.confianca, p.divergente = combinar(regra, p.tipo_llm, p.conf_llm)

    p.status, p.erro = "ok", None
    db.commit()


def _contexto_anterior(db: Session, p: Pagina) -> str | None:
    ant = db.scalar(select(Pagina).where(Pagina.lote_id == p.lote_id, Pagina.numero == p.numero - 1,
                                         Pagina.status == "ok"))
    if not ant:
        return None
    if ant.em_branco:
        return "página em branco"
    return f"tipo={ant.tipo}; final do texto: \"{(ant.texto or '')[-300:]}\""


# ---------------------------------------------------------------- etapas 4-5
def finalizar_lote_se_pronto(db: Session, lote_id: str) -> bool:
    abertas = db.scalar(select(func.count()).select_from(Pagina)
                        .where(Pagina.lote_id == lote_id, Pagina.status.in_(STATUS_EM_ABERTO)))
    if abertas:
        return False
    # "trava" otimista: só UM worker consegue mudar processando → segmentando
    res = db.execute(update(Lote).where(Lote.id == lote_id, Lote.status == "processando")
                     .values(status="segmentando", atualizado_em=agora()))
    db.commit()
    if res.rowcount != 1:
        return False

    lote = db.get(Lote, lote_id)
    try:
        segmentar_e_montar(db, lote)
        lote.status, lote.erro = "concluido", None
    except Exception as e:
        log.exception("falha ao segmentar lote %s", lote_id)
        db.rollback()
        lote = db.get(Lote, lote_id)
        lote.status, lote.erro = "erro", str(e)[:2000]
    db.commit()
    return True


def segmentar_e_montar(db: Session, lote: Lote) -> None:
    st = get_storage()
    # idempotência: se for reprocessamento, apaga a segmentação anterior
    for d in list(lote.documentos):
        for k in (d.pdf_key, d.pdf_anon_key):
            if k:
                st.delete(k)
        db.delete(d)
    for p in lote.paginas:
        p.documento_id = None
    db.flush()

    infos = [PaginaInfo(numero=p.numero, tipo=p.tipo or DESCONHECIDO, conf_tipo=p.confianca or 0.0,
                        em_branco=p.em_branco, falhou=p.status == "falhou", divergente=p.divergente,
                        ocr_conf=p.ocr_confianca if p.ocr_confianca is not None else 0.0,
                        inicio_llm=p.inicio_llm, sinais=p.sinais or {})
             for p in lote.paginas]
    por_numero = {p.numero: p for p in lote.paginas}

    for ordem, dp in enumerate(segmentar(infos)):
        doc = Documento(lote_id=lote.id, ordem=ordem, tipo=dp.tipo,
                        pagina_inicio=min(dp.paginas), pagina_fim=max(dp.paginas),
                        confianca=dp.confianca, motivos=dp.motivos,
                        status_revisao="pendente" if dp.revisao else "auto_aprovado")
        db.add(doc)
        db.flush()
        pags = [por_numero[n] for n in dp.paginas]
        for p in pags:
            p.documento_id = doc.id
        gerar_arquivos(lote, doc, pags)
    db.commit()


def gerar_arquivos(lote: Lote, doc: Documento, paginas: list[Pagina]) -> None:
    """(Re)gera PDF pesquisável + PDF anonimizado de um documento. Chamado também após revisão."""
    st = get_storage()
    caminho = st.caminho_local(lote.arquivo_key)
    doc.pdf_key = key_documento(lote.id, doc.id)
    doc.pdf_anon_key = key_documento(lote.id, doc.id, anon=True)
    st.put_bytes(doc.pdf_key, montar_pdf(st, caminho, paginas), "application/pdf")
    st.put_bytes(doc.pdf_anon_key, montar_pdf(st, caminho, paginas, anonimizar=True), "application/pdf")
    doc.texto = "\n\n".join(p.texto or "" for p in paginas)
    if paginas:
        doc.pagina_inicio, doc.pagina_fim = paginas[0].numero, paginas[-1].numero
