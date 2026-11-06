"""Upload e acompanhamento de lotes."""
import hashlib
import io
import json
import logging
import os
import tempfile
import zipfile

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app import util
from app.api.deps import UsuarioAtual, admin, analista, revisor
from app.api.documentos import doc_out
from app.config import settings
from app.db import get_db
from app.llm import contador, obter_llm
from app.models import ConviteFornecedor, Lote, Pagina, RegraSeparacao, Revisao, Trabalhador, VersaoLote, novo_id
from app.pipeline import avaliacao, fraude, multidoc, privacidade, rasterizar, regras_separacao
from app.pipeline.rasterizar import contar_paginas
from app.schemas import DocumentoOut, LoteOut, PaginaOut
from app.status import StatusLote, StatusPagina
from app.storage import get_storage, key_original
from app.tipos import PRIORIDADES

router = APIRouter(prefix="/lotes", tags=["lotes"])

log = logging.getLogger(__name__)

# assinatura (primeiros bytes, em hexadecimal) de cada formato aceito: a extensão sozinha não prova nada
_TIFF = (bytes.fromhex("49492a00"), bytes.fromhex("4d4d002a"))          # II*. (little endian) / MM.* (big endian)
_JPEG = (bytes.fromhex("ffd8ff"),)
ASSINATURAS = {
    ".pdf": (b"%PDF-",),
    ".tif": _TIFF, ".tiff": _TIFF,
    ".png": (bytes.fromhex("89504e470d0a1a0a"),),
    ".jpg": _JPEG, ".jpeg": _JPEG,
}


def conteudo_confere(caminho: str, ext: str) -> bool:
    with open(caminho, "rb") as f:
        inicio = f.read(1024)
    if ext == ".pdf":                      # o PDF pode ter alguns bytes antes do cabeçalho
        return b"%PDF-" in inicio
    return any(inicio.startswith(a) for a in ASSINATURAS.get(ext, ()))


MIMES = {".pdf": "application/pdf", ".tif": "image/tiff", ".tiff": "image/tiff",
         ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def lote_out(db: Session, lote: Lote) -> LoteOut:
    feitas = db.scalar(select(func.count()).select_from(Pagina)
                       .where(Pagina.lote_id == lote.id, Pagina.status.in_((StatusPagina.OK, StatusPagina.FALHOU)))) or 0
    out = LoteOut.model_validate(lote)
    if lote.convite_id:
        convite = db.get(ConviteFornecedor, lote.convite_id)
        out.fornecedor = convite.fornecedor_nome if convite else None
    out.paginas_processadas = feitas
    out.progresso = round(feitas / lote.total_paginas, 3) if lote.total_paginas else 0.0
    return out


async def _receber_arquivo(arquivo: UploadFile, destino: str) -> tuple[str, int]:
    """Grava o upload em blocos de 1 MB (nunca carrega um lote de 1 GB na memória). Retorna (sha256, tamanho)."""
    sha, tamanho, limite = hashlib.sha256(), 0, settings.MAX_UPLOAD_MB * 1024 * 1024
    with open(destino, "wb") as f:
        while bloco := await arquivo.read(1024 * 1024):
            tamanho += len(bloco)
            if tamanho > limite:
                raise HTTPException(413, f"Arquivo maior que {settings.MAX_UPLOAD_MB} MB")
            sha.update(bloco)
            f.write(bloco)
    return sha.hexdigest(), tamanho


def _validar_arquivo(caminho: str, ext: str) -> int:
    """Confere o conteúdo (não só a extensão) e conta as páginas. Retorna o nº de páginas."""
    if not conteudo_confere(caminho, ext):
        raise HTTPException(415, f"O conteúdo do arquivo não é um {ext.lstrip('.').upper()} de verdade")
    try:
        n = contar_paginas(caminho)
    except Exception as e:
        log.info("arquivo rejeitado: %s", e)
        raise HTTPException(422, "Não consegui abrir o arquivo (corrompido ou protegido por senha)") from e
    if n == 0:
        raise HTTPException(422, "Arquivo sem páginas")
    return n


@router.post("", response_model=LoteOut, status_code=201)
async def criar_lote(arquivo: UploadFile = File(...), nome: str | None = Form(None),
                     prioridade: str = Form("media", description="alta | media | baixa — lotes de prioridade alta são processados primeiro"),
                     regras: str | None = Form(None, max_length=2000,
                                               description="regras de separação em português SÓ para este lote"),
                     db: Session = Depends(get_db), u: UsuarioAtual = Depends(analista)):
    prioridade = (prioridade or "media").lower().replace("normal", "media")
    if prioridade not in PRIORIDADES:
        raise HTTPException(422, "prioridade deve ser alta, media ou baixa")
    ext = os.path.splitext(arquivo.filename or "")[1].lower()
    if ext not in settings.extensoes:
        raise HTTPException(415, f"Extensão {ext or '(nenhuma)'} não suportada. Use: {settings.EXTENSOES_PERMITIDAS}")

    fd, tmp = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    try:
        digest, tamanho = await _receber_arquivo(arquivo, tmp)
        existente = db.scalar(select(Lote).where(Lote.hash_sha256 == digest))
        if existente:
            raise HTTPException(409, {"mensagem": "Este arquivo já foi enviado", "lote_id": existente.id})
        lote = criar_lote_de_arquivo(db, nome or arquivo.filename or "lote", tmp, ext, digest, tamanho,
                                     enviado_por=u.login, prioridade=PRIORIDADES[prioridade], regras_texto=regras)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return lote_out(db, lote)


def criar_lote_de_arquivo(db: Session, nome: str, caminho: str, ext: str, digest: str, tamanho: int, *,
                          enviado_por: str | None, prioridade: int, origem: str = "interno",
                          convite_id: int | None = None, regras_texto: str | None = None,
                          max_paginas: int | None = None) -> Lote:
    """Cria o lote a partir de um arquivo já recebido em disco (upload interno e portal do fornecedor usam esta
    mesma função): confere o conteúdo, conta páginas, guarda no storage, cria o Lote e a fila de páginas.
    Recebe um caminho e não bytes: lote de 1 GB nunca vai inteiro para a memória."""
    if not conteudo_confere(caminho, ext):
        raise HTTPException(415, f"O conteúdo do arquivo não é um {ext.lstrip('.').upper()} de verdade")
    lote_id = novo_id()
    original_key, multidoc_info, normalizado = None, None, None
    if settings.MULTIDOC_ATIVO and tamanho <= settings.MULTIDOC_MAX_MB * 1024 * 1024:
        with open(caminho, "rb") as f:
            r = multidoc.normalizar_arquivo(f.read(), f"arquivo{ext}")
        if r:   # várias folhas numa página: o lote passa a usar o PDF normalizado (o hash segue o do original)
            original_key = f"lotes/{lote_id}/original_enviado{ext}"
            get_storage().put_file(original_key, caminho)
            fd, normalizado = tempfile.mkstemp(suffix=".pdf")
            with os.fdopen(fd, "wb") as f:
                f.write(r[0])
            caminho, ext, tamanho, multidoc_info = normalizado, ".pdf", len(r[0]), r[1]
    try:
        return _registrar_lote(db, lote_id, nome, caminho, ext, digest, tamanho, enviado_por=enviado_por,
                               prioridade=prioridade, origem=origem, convite_id=convite_id, regras_texto=regras_texto,
                               max_paginas=max_paginas, original_key=original_key, multidoc_info=multidoc_info)
    finally:
        if normalizado and os.path.exists(normalizado):
            os.unlink(normalizado)


def _registrar_lote(db: Session, lote_id: str, nome: str, caminho: str, ext: str, digest: str, tamanho: int, *,
                    enviado_por, prioridade, origem, convite_id, regras_texto, max_paginas, original_key,
                    multidoc_info) -> Lote:
    n = _validar_arquivo(caminho, ext)
    if max_paginas and n > max_paginas:
        raise HTTPException(422, f"Arquivo com {n} páginas; o limite é {max_paginas}")
    alertas_arquivo = fraude.analisar_pdf(caminho)        # metadados do PDF (editor, modificação)
    key = key_original(lote_id, ext)
    get_storage().put_file(key, caminho)
    lote = Lote(id=lote_id, nome=nome, arquivo_key=key, hash_sha256=digest,
                mime=MIMES.get(ext, "application/octet-stream"), tamanho_bytes=tamanho,
                total_paginas=n, status=StatusLote.PROCESSANDO, prioridade=prioridade,
                enviado_por=enviado_por, alertas=alertas_arquivo, origem=origem, convite_id=convite_id,
                arquivo_original_key=original_key, multidoc=multidoc_info,
                regras_aplicadas=retrato_das_regras(db, regras_texto))
    db.add(lote)
    db.add_all(Pagina(lote_id=lote_id, numero=i) for i in range(n))   # fila de trabalho = as páginas
    try:
        db.commit()
    except Exception:
        db.rollback()
        for k in (key, original_key):
            try:
                if k:
                    get_storage().delete(k)
            except Exception:
                log.exception("Falha ao remover arquivo após erro ao registrar lote")
        raise
    return lote


@router.get("", response_model=list[LoteOut])
def listar_lotes(db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    return [lote_out(db, lt) for lt in db.scalars(select(Lote).order_by(Lote.criado_em.desc()).limit(100))]


def retrato_das_regras(db: Session, texto_extra: str | None = None) -> list[dict]:
    """Regras ativas agora (+ as escritas no upload, só para este lote): o lote guarda o retrato, e reprocessar
    dá o mesmo resultado mesmo que alguém mude as regras depois."""
    retrato = [{"texto": r.texto, "estruturada": r.estruturada}
               for r in db.scalars(select(RegraSeparacao).where(RegraSeparacao.ativa.is_(True)).order_by(RegraSeparacao.id))]
    if texto_extra and texto_extra.strip():
        estruturada, _ = regras_separacao.interpretar(texto_extra, obter_llm())
        if estruturada:
            retrato.append({"texto": texto_extra.strip()[:500], "estruturada": estruturada})
    return retrato


def _obter(db: Session, lote_id: str) -> Lote:
    lote = db.get(Lote, lote_id)
    if not lote:
        raise HTTPException(404, "Lote não encontrado")
    return lote


@router.get("/{lote_id}", response_model=LoteOut)
def obter_lote(lote_id: str, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    return lote_out(db, _obter(db, lote_id))


@router.get("/{lote_id}/paginas", response_model=list[PaginaOut])
def paginas_do_lote(lote_id: str, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    return _obter(db, lote_id).paginas


@router.get("/{lote_id}/documentos", response_model=list[DocumentoOut])
def documentos_do_lote(lote_id: str, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    return [doc_out(d) for d in _obter(db, lote_id).documentos]


@router.post("/{lote_id}/reprocessar", response_model=LoteOut)
def reprocessar(lote_id: str, tudo: bool = False, atualizar_regras: bool = False, db: Session = Depends(get_db),
                u: UsuarioAtual = Depends(revisor)):
    """Recoloca na fila as páginas que falharam (ou todas, com ?tudo=true). Usa o retrato de regras de separação
    do lote; ?atualizar_regras=true troca pelo retrato das regras ativas agora."""
    lote = _obter(db, lote_id)
    if lote.status in ("processando", "segmentando"):
        raise HTTPException(409, "Aguarde o processamento atual terminar.")
    cond = [Pagina.lote_id == lote_id]
    if not tudo:
        cond.append(Pagina.status.in_((StatusPagina.ERRO, StatusPagina.FALHOU)))
    if not db.scalar(select(func.count()).select_from(Pagina).where(*cond)):
        raise HTTPException(409, "Nenhuma página para reprocessar.")
    if lote.documentos:
        def retrato(obj):
            return json.loads(json.dumps({col.name: getattr(obj, col.name) for col in obj.__table__.columns},
                                         default=str, ensure_ascii=False))
        versao = VersaoLote(lote_id=lote_id, usuario=u.login, dados={
            "documentos": [retrato(d) for d in lote.documentos],
            "paginas": [retrato(p) for p in lote.paginas],
            "revisoes": [retrato(r) for r in db.scalars(select(Revisao).where(Revisao.lote_id == lote_id))],
        })
        db.add(versao)
    numeros = list(db.scalars(select(Pagina.numero).where(*cond)))
    contador.zerar(db, lote_id, numeros)
    if atualizar_regras:
        lote.regras_aplicadas = retrato_das_regras(db)          # o contador de IA reflete só a última execução
    db.execute(update(Pagina).where(*cond).values(status=StatusPagina.PENDENTE, tentativas=0, erro=None))
    lote.status, lote.erro = StatusLote.PROCESSANDO, None
    db.commit()
    return lote_out(db, lote)


@router.get("/{lote_id}/versoes")
def versoes_do_lote(lote_id: str, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(revisor)):
    """Resultados e revisões preservados antes de cada reprocessamento."""
    _obter(db, lote_id)
    versoes = db.scalars(select(VersaoLote).where(VersaoLote.lote_id == lote_id).order_by(VersaoLote.id.desc()))
    return [{"id": v.id, "criado_em": v.criado_em, "usuario": v.usuario, **v.dados} for v in versoes]


@router.get("/{lote_id}/versoes/{versao_id}/documentos/{documento_id}/pdf")
def pdf_da_versao(lote_id: str, versao_id: int, documento_id: str, anonimizado: bool = True,
                  db: Session = Depends(get_db), _u: UsuarioAtual = Depends(revisor)):
    versao = db.get(VersaoLote, versao_id)
    if not versao or versao.lote_id != lote_id:
        raise HTTPException(404, "Versão não encontrada")
    documento = next((d for d in versao.dados.get("documentos", []) if d["id"] == documento_id), None)
    key = documento and documento.get("pdf_anon_key" if anonimizado else "pdf_key")
    if not key:
        raise HTTPException(404, "PDF da versão não encontrado")
    try:
        conteudo = get_storage().get_bytes(key)
    except FileNotFoundError:
        raise HTTPException(404, "PDF da versão não encontrado no armazenamento") from None
    return Response(conteudo, media_type="application/pdf")
@router.delete("/{lote_id}")
def apagar_lote(lote_id: str, db: Session = Depends(get_db), u: UsuarioAtual = Depends(admin)):
    """LGPD (direito de eliminação): apaga o lote, as páginas, os documentos, os arquivos no storage e as
    pessoas que ficarem sem nenhum documento. Fica só um registro de auditoria SEM dados pessoais."""
    lote = _obter(db, lote_id)
    if lote.status in (StatusLote.PROCESSANDO, StatusLote.SEGMENTANDO):
        raise HTTPException(409, "Lote em processamento; aguarde terminar para apagar")
    resumo = {"nome": lote.nome, "paginas": lote.total_paginas, "documentos": len(lote.documentos)}
    caminho = get_storage().caminho_local(lote.arquivo_key) if settings.STORAGE_BACKEND == "local" else None
    if caminho:
        rasterizar.fechar(caminho)         # libera o arquivo aberto em cache (no Windows, senão não apaga)
    pessoas = {d.trabalhador_id for d in lote.documentos if d.trabalhador_id}
    db.delete(lote)
    db.flush()
    for t in db.scalars(select(Trabalhador).where(Trabalhador.id.in_(pessoas))):
        if not t.documentos:
            db.delete(t)
    db.add(Revisao(documento_id=None, lote_id=lote_id, usuario=u.login, acao="lote_apagado", antes=resumo))
    db.commit()
    get_storage().delete_prefixo(f"lotes/{lote_id}/")
    return {"apagado": lote_id} | resumo


@router.get("/{lote_id}/privacidade")
def risco_de_privacidade(lote_id: str, limite: int = Query(100, ge=1, le=1000, description="máx. de documentos sensíveis detalhados"),
                         db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    """Relatório de risco de privacidade (para o encarregado de dados): quantos CPFs, nomes, endereços..., quantas
    pessoas distintas e quais documentos têm dados sensíveis (saúde, biometria, filiação sindical). Só números e
    evidências: nenhum dado pessoal é devolvido. Use antes de compartilhar o lote."""
    lote = _obter(db, lote_id)
    if lote.status != StatusLote.CONCLUIDO:
        raise HTTPException(409, f"Lote ainda não concluído (status: {lote.status})")
    return privacidade.relatorio_do_lote(db, lote, limite)


@router.put("/{lote_id}/gabarito")
def definir_gabarito(lote_id: str, gabarito: dict = Body(..., examples=[{"lote": "lote_terceiros.pdf", "documentos": [
                         {"tipo": "ASO", "paginas": [0]}, {"tipo": "CONTRATO", "paginas": [11, 12]}]}]),
                     db: Session = Depends(get_db), _u: UsuarioAtual = Depends(revisor)):
    """Grava a verdade conhecida do lote (páginas 0-based) para medir o acerto em GET /lotes/{id}/avaliacao."""
    lote = _obter(db, lote_id)
    try:
        lote.gabarito = avaliacao.validar_gabarito(gabarito, lote.total_paginas)
    except ValueError as e:
        raise HTTPException(422, f"Gabarito inválido: {e}") from e
    db.commit()
    return {"lote_id": lote.id, "documentos": len(lote.gabarito)}


@router.get("/{lote_id}/avaliacao")
def avaliar_acerto(lote_id: str, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    """% de acerto contra o gabarito: cortes, documentos exatos, tipo e erros silenciosos (auto-aprovados errados)."""
    lote = _obter(db, lote_id)
    if not lote.gabarito:
        raise HTTPException(409, "Lote sem gabarito")
    if lote.status != StatusLote.CONCLUIDO:
        raise HTTPException(409, f"Lote ainda não concluído (status: {lote.status})")
    revisado = db.scalar(select(func.count()).select_from(Revisao).where(Revisao.lote_id == lote.id)) > 0
    return {"lote_id": lote.id, "metricas": avaliacao.comparar(lote.gabarito, previstos_do_lote(db, lote)),
            "com_revisao_humana": revisado,
            "aviso": ("O lote tem correções humanas; as métricas medem o resultado final, não só a máquina."
                      if revisado else None)}


def previstos_do_lote(db: Session, lote: Lote) -> list[dict]:
    """Documentos do sistema no formato de avaliacao.comparar (páginas reais de cada documento)."""
    paginas: dict[str, list[int]] = {}
    for doc_id, numero in db.execute(select(Pagina.documento_id, Pagina.numero)
                                     .where(Pagina.lote_id == lote.id, Pagina.documento_id.is_not(None))):
        paginas.setdefault(doc_id, []).append(numero)
    return [{"id": d.id, "tipo": d.tipo, "status_revisao": d.status_revisao, "paginas": sorted(paginas.get(d.id, []))}
            for d in lote.documentos]


@router.get("/{lote_id}/zip")
def baixar_zip(lote_id: str, anonimizado: bool = True, db: Session = Depends(get_db),
               u: UsuarioAtual = Depends(analista)):
    """Todos os documentos do lote num .zip, um PDF por documento, nomeados por ordem e tipo,
    mais um manifesto.json (tipo, páginas, validade, prioridade, resumo)."""
    if not anonimizado and u.autenticado and u.perfil == "analista":
        raise HTTPException(403, "O PDF original (com dados pessoais) exige perfil revisor ou superior")
    lote = _obter(db, lote_id)
    if lote.status != StatusLote.CONCLUIDO:
        raise HTTPException(409, f"Lote ainda não concluído (status: {lote.status})")
    st, buf, manifesto = get_storage(), io.BytesIO(), []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for d in lote.documentos:
            key = d.pdf_anon_key if anonimizado else d.pdf_key
            if not key:
                continue
            nome = f"{d.ordem + 1:03d}_{d.tipo.lower()}{'_anon' if anonimizado else ''}.pdf"
            z.writestr(nome, st.get_bytes(key))
            if anonimizado:
                manifesto.append({"id": d.id, "ordem": d.ordem, "tipo": d.tipo,
                                   "pagina_inicio": d.pagina_inicio, "pagina_fim": d.pagina_fim,
                                   "validade": {"status": doc_out(d).validade.status}, "arquivo": nome})
            else:
                manifesto.append(doc_out(d).model_dump(mode="json") | {"arquivo": nome})
        nome_lote = f"Lote {lote.id}" if anonimizado else lote.nome
        z.writestr("manifesto.json", json.dumps({"lote": nome_lote, "lote_id": lote.id, "documentos": manifesto},
                                                ensure_ascii=False, indent=2))
    nome_zip = f"lote_{lote.id}_documentos.zip" if anonimizado else f"{os.path.splitext(lote.nome)[0]}_documentos.zip"
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": util.content_disposition(nome_zip)})


@router.get("/{lote_id}/paginas/{numero}/imagem")
def imagem_pagina(lote_id: str, numero: int, thumb: bool = True, db: Session = Depends(get_db),
                  u: UsuarioAtual = Depends(analista)):
    if u.autenticado and u.perfil == "analista":
        raise HTTPException(403, "As imagens originais e miniaturas exigem perfil revisor ou superior")
    p = db.scalar(select(Pagina).where(Pagina.lote_id == lote_id, Pagina.numero == numero))
    key = p and (p.thumb_key if thumb else p.imagem_key)
    if not key:
        raise HTTPException(404, "Imagem ainda não gerada")
    try:
        conteudo = get_storage().get_bytes(key)
    except FileNotFoundError:
        raise HTTPException(404, "Imagem da página não encontrada no armazenamento") from None
    return Response(conteudo, media_type="image/jpeg" if thumb else "image/png",
                    headers={"Cache-Control": "private, max-age=3600"})
