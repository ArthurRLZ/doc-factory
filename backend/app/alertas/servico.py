"""Quais documentos avisar, em que faixa, para quem — e o registro que impede repetir o aviso.

Decisões (F6):
  - quem recebe: os ContatoAlerta ativos, com UM resumo agregado por contato (não 1 mensagem por documento);
  - quando: a faixa ATUAL do documento (a menor faixa f com dias <= f; vencido se dias < 0). Um documento enviado
    a 3 dias do vencimento gera só a faixa "7", não 30 + 15 + 7;
  - sem repetição: AlertaEnviado é único por (documento, contato, canal, faixa); falha não conta como enviado;
  - só o documento MAIS RECENTE de cada (trabalhador, tipo) — o substituído não gera aviso;
  - nada de CPF completo nem texto do documento na mensagem.
"""
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import util
from app.alertas.canais import ErroEnvio, obter_canal
from app.config import settings
from app.models import AlertaEnviado, Configuracao, ContatoAlerta, Documento, Lote
from app.pipeline import validade
from app.pipeline.checklist import _mais_recente
from app.status import StatusLote
from app.tipos import TIPOS_COM_VALIDADE, nome_tipo

log = logging.getLogger(__name__)

CHAVE_ULTIMA_EXECUCAO = "alertas_ultima_execucao"
LIMITE_MENSAGEM = 3500
STATUS_OK = ("enviado", "simulado")


def faixa_do_documento(dias: int, faixas: list[int]) -> str | None:
    """dias=3, [30,15,7,1] → "7"; dias=0 → "1"; dias=-2 → "vencido"; dias=45 → None."""
    if dias < 0:
        return "vencido"
    for f in sorted(faixas):
        if dias <= f:
            return str(f)
    return None


def candidatos(db: Session, hoje: date | None = None) -> list[dict]:
    hoje = hoje or util.hoje()
    faixas = settings.alertas_faixas
    docs = db.scalars(select(Documento).join(Lote).where(
        Documento.validade_data.is_not(None), Documento.tipo.in_(TIPOS_COM_VALIDADE),
        Lote.status != StatusLote.ERRO))
    grupos: dict[tuple, list[Documento]] = {}
    for d in docs:
        grupos.setdefault((d.trabalhador_id, d.tipo), []).append(d)
    base = settings.ALERTAS_URL_PUBLICA.rstrip("/")
    itens = []
    for grupo in grupos.values():
        d = _mais_recente(grupo)                       # o substituído não gera aviso
        st, dias = validade.status(d.validade_data, d.tipo, hoje)
        if dias is None:
            continue
        faixa = faixa_do_documento(dias, faixas)
        if not faixa:
            continue
        itens.append({"documento_id": d.id, "tipo": d.tipo, "tipo_nome": nome_tipo(d.tipo),
                      "trabalhador": f"Trabalhador {d.trabalhador.cpf_mascarado}" if d.trabalhador else None,
                      "validade": d.validade_data.isoformat(), "dias": dias, "faixa": faixa,
                      "status_validade": st, "lote_nome": d.lote.nome,
                      "documento_url": f"{base}/documentos?documento={d.id}"})
    itens.sort(key=lambda i: (i["dias"], i["tipo_nome"]))
    return itens


def _linha(i: dict) -> str:
    quem = i["trabalhador"] or "empresa"
    if i["dias"] < 0:
        quando = f"venceu há {abs(i['dias'])} dia(s)"
    elif i["dias"] == 0:
        quando = "vence hoje"
    else:
        quando = f"vence em {i['dias']} dia(s)"
    return f"• {i['tipo_nome']} — {quem} — {quando} (Lote {i['lote_nome']})"


def _ordem_faixa(f: str) -> int:
    return -1 if f == "vencido" else int(f)


def montar_mensagem(itens: list[dict], canal: str) -> tuple[str, str]:
    """(assunto, texto) em português, agrupado por faixa (vencidos primeiro). Emoji só no WhatsApp."""
    vencidos = sum(1 for i in itens if i["faixa"] == "vencido")
    assunto = f"Document Factory: {len(itens)} documento(s) vencendo ou vencidos" + (
        f" ({vencidos} vencido(s))" if vencidos else "")
    linhas = [("⚠️ " if canal == "whatsapp" else "") + "Document Factory — vencimentos de documentos"]
    por_faixa: dict[str, list[dict]] = {}
    for i in itens:
        por_faixa.setdefault(i["faixa"], []).append(i)
    for faixa in sorted(por_faixa, key=_ordem_faixa):
        linhas.append("VENCIDOS" if faixa == "vencido" else f"VENCEM EM ATÉ {faixa} DIA(S)")
        linhas += [_linha(i) for i in por_faixa[faixa]]
    rodape = f"Abra: {settings.ALERTAS_URL_PUBLICA.rstrip('/')}/vencimentos"
    texto = "\n".join(linhas + [rodape])
    if len(texto) > LIMITE_MENSAGEM:                   # corta a lista e avisa quantos ficaram de fora
        corpo, tamanho, usados = [], 0, 0
        for ln in linhas:
            if tamanho + len(ln) + len(rodape) + 60 > LIMITE_MENSAGEM:
                break
            corpo.append(ln)
            tamanho += len(ln) + 1
            usados += ln.startswith("•")
        texto = "\n".join(corpo + [f"… e mais {len(itens) - usados} documento(s)", rodape])
    return assunto, texto


def _ja_avisados(db: Session, contato: ContatoAlerta) -> set[tuple[str, str]]:
    return {tuple(r) for r in db.execute(select(AlertaEnviado.documento_id, AlertaEnviado.faixa).where(
        AlertaEnviado.contato_id == contato.id, AlertaEnviado.canal == contato.canal,
        AlertaEnviado.status.in_(STATUS_OK))).all()}


def _registrar(db: Session, item: dict, contato: ContatoAlerta, status: str, erro: str | None) -> None:
    """Grava/atualiza o registro do aviso. Um 'falhou' anterior da mesma chave é reaproveitado (permite retentar);
    corrida entre dois workers (unique) é ignorada."""
    chave = (AlertaEnviado.documento_id == item["documento_id"], AlertaEnviado.contato_id == contato.id,
             AlertaEnviado.canal == contato.canal, AlertaEnviado.faixa == item["faixa"])
    existente = db.scalar(select(AlertaEnviado).where(*chave))
    if existente:
        if existente.status not in STATUS_OK:
            existente.status, existente.erro, existente.enviado_em = status, erro, datetime.now(timezone.utc)
        return
    try:
        with db.begin_nested():
            db.add(AlertaEnviado(documento_id=item["documento_id"], contato_id=contato.id, canal=contato.canal,
                                 faixa=item["faixa"], status=status, erro=erro))
    except IntegrityError:
        log.info("aviso já registrado por outro processo (documento %s)", item["documento_id"])


def pendentes(db: Session, hoje: date | None = None) -> list[dict]:
    """Prévia: o que seria enviado agora, por contato (não envia nem grava)."""
    cands = candidatos(db, hoje)
    saida = []
    for contato in db.scalars(select(ContatoAlerta).where(ContatoAlerta.ativo.is_(True)).order_by(ContatoAlerta.id)):
        feitos = _ja_avisados(db, contato)
        novos = [i for i in cands if (i["documento_id"], i["faixa"]) not in feitos]
        if novos:
            assunto, texto = montar_mensagem(novos, contato.canal)
            saida.append({"contato_id": contato.id, "contato": contato.nome, "canal": contato.canal,
                          "itens": novos, "assunto": assunto, "texto": texto})
    return saida


def executar(db: Session, simular: bool | None = None, agora: datetime | None = None) -> dict:
    hoje = (agora + timedelta(hours=settings.FUSO_HORAS)).date() if agora else util.hoje()
    modo_simulado = simular if simular is not None else settings.ALERTAS_MODO != "real"
    resumo = {"contatos": 0, "mensagens": 0, "itens": 0, "falhas": 0, "simulado": modo_simulado}
    for p in pendentes(db, hoje):
        contato = db.get(ContatoAlerta, p["contato_id"])
        resumo["contatos"] += 1
        try:
            obter_canal(contato.canal, simular=modo_simulado).enviar(contato.destino, p["assunto"], p["texto"])
            status, erro = ("simulado" if modo_simulado else "enviado"), None
            resumo["mensagens"] += 1
            resumo["itens"] += len(p["itens"])
        except ErroEnvio as e:
            status, erro = "falhou", str(e)[:500]
            resumo["falhas"] += 1
            log.warning("alerta para o contato %s falhou: %s", contato.id, erro)
        for item in p["itens"]:
            _registrar(db, item, contato, status, erro)
        db.commit()
    return resumo


def rodar_agendado(db: Session, agora: datetime | None = None) -> dict | None:
    """No máximo 1x por dia local, a partir de ALERTAS_HORA_EXECUCAO. Só UM processo 'reserva' o dia
    (UPDATE condicional); se o envio explodir, a reserva é desfeita para tentar de novo no próximo ciclo."""
    agora = agora or datetime.now(timezone.utc)
    local = agora + timedelta(hours=settings.FUSO_HORAS)
    if local.hour < settings.ALERTAS_HORA_EXECUCAO:
        return None
    hoje = local.date().isoformat()
    atual = db.get(Configuracao, CHAVE_ULTIMA_EXECUCAO)
    anterior = atual.valor if atual else None
    if atual is None:
        try:
            db.add(Configuracao(chave=CHAVE_ULTIMA_EXECUCAO, valor=hoje, alterado_por="worker"))
            db.commit()
        except IntegrityError:
            db.rollback()
            return None
    else:
        res = db.execute(update(Configuracao).where(Configuracao.chave == CHAVE_ULTIMA_EXECUCAO,
                                                    Configuracao.valor != hoje).values(valor=hoje))
        db.commit()
        if res.rowcount != 1:
            return None
    try:
        return executar(db, agora=agora)
    except Exception:
        db.rollback()
        log.exception("falha ao enviar os alertas de vencimento; tenta de novo no próximo ciclo")
        tabela = Configuracao.__table__
        if anterior is None:
            db.execute(tabela.delete().where(tabela.c.chave == CHAVE_ULTIMA_EXECUCAO))
        else:
            db.execute(tabela.update().where(tabela.c.chave == CHAVE_ULTIMA_EXECUCAO).values(valor=anterior))
        db.commit()
        return None
