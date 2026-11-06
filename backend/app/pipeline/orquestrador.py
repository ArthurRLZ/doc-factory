"""Orquestrador do pipeline — liga as etapas e grava no banco/storage.

processar_pagina()       → etapas 1-3, por página, idempotente (pode rodar 2x sem estragar)
finalizar_lote_se_pronto() → quando TODAS as páginas acabaram, roda etapas 4-5 uma única vez
"""
import logging
from collections import Counter

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.llm import contador, obter_llm
from app.models import Documento, Lote, Pagina, Trabalhador, VersaoLote, agora
from app.pipeline import aprendizado, fraude, funcao, identidade, pre_revisao, rasterizar
from app.pipeline.explicabilidade import decidido_por
from app.pipeline.anonimizar import indices_sensiveis, mascarar_texto, tarjar_imagem
from app.pipeline.automacao import obter_limiar
from app.pipeline.classificar import (
    classificar_por_regras,
    combinar,
    sinais_de_inicio,
    texto_do_topo,
)
from app.pipeline.montar import montar_pdf
from app.pipeline.ocr import e_pagina_em_branco, ocr_png
from app.pipeline.resumir import resumir_documento
from app.pipeline.segmentar import PaginaInfo, segmentar
from app.storage import get_storage, key_documento, key_pagina
from app.tipos import DESCONHECIDO, TIPOS_DO_TRABALHADOR
from app.status import PAGINAS_EM_ABERTO, StatusLote, StatusPagina, StatusRevisao

log = logging.getLogger(__name__)

STATUS_EM_ABERTO = PAGINAS_EM_ABERTO


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
        o = ocr_png(r.png, r.dpi)
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
        p.tipo, p.confianca, p.tipo_regra, p.conf_regra = DESCONHECIDO, 0.0, DESCONHECIDO, 0.0
        p.sinais = {"conteudo_incerto": True} if not r.nativa and o.conteudo_incerto else {}
    else:
        topo = texto_do_topo(palavras, r.altura_pt)
        regra = classificar_por_regras(texto or "", topo, aprendizado.regras(db))
        p.tipo_regra, p.conf_regra = regra.tipo, regra.confianca
        p.sinais = sinais_de_inicio(texto or "", topo) | {"scores": regra.scores}
        if not texto or not texto.strip():
            p.sinais = p.sinais | {"sem_texto_para_revisao": True}
        if regra.aprendizado_id:            # uma correção humana anterior decidiu esta página
            p.sinais = p.sinais | {"aprendizado": regra.aprendizado_id}
            aprendizado.contar_uso(db, regra.aprendizado_id)

        llm = obter_llm()
        if llm and (settings.LLM_SEMPRE or regra.confianca < settings.LIMIAR_LLM):
            imagem_segura = tarjar_imagem(r.png, palavras, indices_sensiveis(palavras), r.dpi)
            resp = llm.classificar(p.texto, imagem_segura, _contexto_anterior(db, p), aprendizado.exemplos(db))
            contador.registrar(db, p.lote_id, "classificacao", p.id)
            if resp:
                p.tipo_llm, p.conf_llm, p.inicio_llm = resp.tipo, resp.confianca, resp.inicio_documento
                p.sinais = p.sinais | {"llm_justificativa": resp.justificativa}

        p.tipo, p.confianca, p.divergente = combinar(regra, p.tipo_llm, p.conf_llm)
        # chave identificadora: impressão digital dos CPFs da página (lidos ANTES da máscara; o CPF não é guardado)
        p.sinais = p.sinais | {"cpfs": identidade.impressoes(db, texto or "")}

    p.status, p.erro = StatusPagina.OK, None
    db.commit()


def _contexto_anterior(db: Session, p: Pagina) -> str | None:
    ant = db.scalar(select(Pagina).where(Pagina.lote_id == p.lote_id, Pagina.numero == p.numero - 1,
                                         Pagina.status == StatusPagina.OK))
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
    res = db.execute(update(Lote).where(Lote.id == lote_id, Lote.status == StatusLote.PROCESSANDO)
                     .values(status=StatusLote.SEGMENTANDO, atualizado_em=agora()))
    db.commit()
    if res.rowcount != 1:
        return False

    lote = db.get(Lote, lote_id)
    try:
        segmentar_e_montar(db, lote)
        incertas = [p.numero + 1 for p in lote.paginas if (p.sinais or {}).get("conteudo_incerto")]
        alertas = [a for a in (lote.alertas or []) if a.get("codigo") != "paginas_incerto"]
        if incertas:
            alertas.append({"codigo": "paginas_incerto", "gravidade": "media",
                            "mensagem": "Possível conteúdo em páginas consideradas separadoras; confira o arquivo original.",
                            "evidencia": "Páginas: " + ", ".join(map(str, incertas))})
        lote.alertas = alertas
        falhas = db.scalar(select(func.count()).select_from(Pagina).where(
            Pagina.lote_id == lote_id, Pagina.status == StatusPagina.FALHOU)) or 0
        if falhas:
            lote.status = StatusLote.ERRO
            lote.erro = f"{falhas} página(s) não puderam ser processadas. Consulte as páginas e reprocesse o lote."
        else:
            lote.status, lote.erro = StatusLote.CONCLUIDO, None
    except Exception as e:
        log.exception("falha ao segmentar lote %s", lote_id)
        db.rollback()
        lote = db.get(Lote, lote_id)
        lote.status, lote.erro = StatusLote.ERRO, str(e)[:2000]
    db.commit()
    return True


def segmentar_e_montar(db: Session, lote: Lote) -> None:
    st = get_storage()
    # Os arquivos anteriores só são removidos após a nova segmentação ser confirmada.
    antigos = []
    preservados = {d[k] for v in db.scalars(select(VersaoLote).where(VersaoLote.lote_id == lote.id))
                   for d in v.dados.get("documentos", []) for k in ("pdf_key", "pdf_anon_key") if d.get(k)}
    for d in list(lote.documentos):
        antigos.extend(k for k in (d.pdf_key, d.pdf_anon_key) if k and k not in preservados)
        db.delete(d)
    for p in lote.paginas:
        p.documento_id = None
    db.flush()

    infos = [PaginaInfo(numero=p.numero, tipo=p.tipo or DESCONHECIDO, conf_tipo=p.confianca or 0.0,
                        em_branco=p.em_branco, falhou=p.status == StatusPagina.FALHOU, divergente=p.divergente,
                        ocr_conf=p.ocr_confianca if p.ocr_confianca is not None else 0.0,
                        inicio_llm=p.inicio_llm, sinais=p.sinais or {})
             for p in lote.paginas]
    # Mesmo um lote inteiramente branco precisa ser visível para revisão humana.
    # Caso contrário a segmentação descartaria todas as páginas e indicaria sucesso vazio.
    if infos and all(p.em_branco for p in infos):
        for p in infos:
            p.em_branco = False
            p.sinais = {**(p.sinais or {}), "sem_texto_para_revisao": True}
    por_numero = {p.numero: p for p in lote.paginas}

    novos = []
    try:
        regras = [dict(r, texto=item.get("texto")) for item in (lote.regras_aplicadas or [])
                  for r in item.get("estruturada", [])]
        for ordem, dp in enumerate(segmentar(infos, obter_limiar(db), regras)):
            doc = Documento(lote_id=lote.id, ordem=ordem, tipo=dp.tipo,
                            pagina_inicio=min(dp.paginas), pagina_fim=max(dp.paginas),
                            confianca=dp.confianca, motivos=dp.motivos,
                            status_revisao=StatusRevisao.PENDENTE if dp.revisao else StatusRevisao.AUTO_APROVADO,
                            regras_aplicadas=dp.regras_aplicadas or None)
            db.add(doc)
            db.flush()
            novos.extend((key_documento(lote.id, doc.id), key_documento(lote.id, doc.id, anon=True)))
            pags = [por_numero[n] for n in dp.paginas]
            for p in pags:
                p.documento_id = doc.id
            gerar_arquivos(lote, doc, pags)
            atribuir_trabalhador(db, doc, pags)
            resumir_documento(lote, doc)
            doc.decidido_por, doc.ia_justificativa = decidido_por(pags, doc.tipo)
            db.flush()
            fraude.aplicar(db, lote, doc, pags)
        db.flush()
        _atualizar_funcoes(db, lote)
        _pre_revisar(db, lote, por_numero)
        db.commit()
    except Exception:
        db.rollback()
        for key in novos:
            try:
                st.delete(key)
            except Exception:
                log.exception("Falha ao remover arquivo de segmentação não confirmada: %s", key)
        raise
    for key in antigos:
        try:
            st.delete(key)
        except Exception:
            log.exception("Falha ao remover arquivo antigo após segmentação: %s", key)


def _pre_revisar(db: Session, lote: Lote, por_numero: dict[int, Pagina]) -> None:
    """Pendentes ganham explicação + sugestão (F2). Passado o teto de chamadas por lote, só por regras."""
    if not settings.PRE_REVISAO_ATIVA:
        return
    llm, usadas = obter_llm(), 0
    pendentes = db.scalars(select(Documento).where(Documento.lote_id == lote.id,
                                                   Documento.status_revisao == StatusRevisao.PENDENTE)
                           .order_by(Documento.ordem))
    for doc in pendentes:
        pags = [por_numero[n] for n in range(doc.pagina_inicio, doc.pagina_fim + 1) if n in por_numero]
        usar_ia = usadas < settings.PRE_REVISAO_MAX_POR_LOTE
        consulta_ia = (usar_ia and getattr(llm, "pre_revisar", None) is not None and bool((doc.texto or "").strip()))
        doc.pre_revisao = pre_revisao.gerar(db, lote, doc, pags, llm, usar_ia)
        usadas += consulta_ia


def _atualizar_funcoes(db: Session, lote: Lote) -> None:
    """Função de cada trabalhador tocado no lote (F3): define as NRs exigidas no checklist."""
    # consulta direta: as coleções em memória (lote.documentos, t.documentos) podem estar desatualizadas aqui
    ids = set(db.scalars(select(Documento.trabalhador_id).where(Documento.lote_id == lote.id,
                                                               Documento.trabalhador_id.is_not(None))))
    llm = obter_llm()
    for t in db.scalars(select(Trabalhador).where(Trabalhador.id.in_(ids))) if ids else []:
        docs = list(db.scalars(select(Documento).where(Documento.trabalhador_id == t.id)))
        funcao.atualizar_funcao(db, t, docs, llm, lote.id)


def atribuir_trabalhador(db: Session, doc: Documento, paginas: list[Pagina]) -> None:
    """Liga o documento à pessoa cujo CPF mais aparece nas suas páginas (pela impressão digital).
    Só tipos do trabalhador (TIPOS_DO_TRABALHADOR); documentos sem CPF ou da empresa ficam sem trabalhador."""
    if doc.tipo not in TIPOS_DO_TRABALHADOR:
        doc.trabalhador_id = None
        return
    contagem: Counter = Counter()
    mascaras = {}
    for p in paginas:
        for c in (p.sinais or {}).get("cpfs", []):
            contagem[c["h"]] += 1
            mascaras[c["h"]] = c["m"]
    if not contagem:
        doc.trabalhador_id = None
        return
    h = contagem.most_common(1)[0][0]
    t = db.scalar(select(Trabalhador).where(Trabalhador.cpf_hash == h))
    if not t:
        t = Trabalhador(cpf_hash=h, cpf_mascarado=mascaras[h])
        db.add(t)
        db.flush()
    doc.trabalhador_id = t.id


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
