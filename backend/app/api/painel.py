"""Rotas prontas para as telas do front: visão geral (/painel) e relatórios (/relatorios).

Tudo em uma chamada por tela, com os números já calculados (o front só exibe).
"Hoje", "esta semana" e o volume por dia usam o fuso FUSO_HORAS (Brasília = -3).
"""
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import UsuarioAtual, analista
from app.api.documentos import doc_out
from app.config import settings
from app.db import get_db
from app.models import Documento, Lote, Trabalhador
from app.pipeline import checklist, validade
from app.tipos import PRIORIDADE_NOME, setor_do_tipo

router = APIRouter(tags=["telas (painel e relatórios)"])
_DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


def _fuso() -> timezone:
    return timezone(timedelta(hours=settings.FUSO_HORAS))


def _local(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:            # SQLite devolve sem fuso: o valor gravado é UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_fuso())


def _hoje() -> date:
    return datetime.now(_fuso()).date()


def _pct(parte: int, total: int) -> float:
    return round(100 * parte / total, 1) if total else 0.0


def _variacao(atual: int, anterior: int) -> float | None:
    return round(100 * (atual - anterior) / anterior, 1) if anterior else None


def _contagem_por_dia(datas: list[date], inicio: date, dias: int) -> list[dict]:
    c = Counter(datas)
    return [{"data": (inicio + timedelta(days=i)).isoformat(), "total": c.get(inicio + timedelta(days=i), 0)}
            for i in range(dias)]


def _status_validade(docs: list[Documento]) -> Counter:
    return Counter(validade.status(d.validade_data, d.tipo)[0] for d in docs)


@router.get("/painel")
def painel(db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    """Tela "Visão geral": cartões, volume de 7 dias, itens de atenção, recentes e distribuição por setor."""
    hoje = _hoje()
    docs = list(db.scalars(select(Documento)))
    criados = [(d, _local(d.criado_em).date()) for d in docs]
    pendentes = [d for d in docs if d.status_revisao == "pendente"]
    st = {d.id: validade.status(d.validade_data, d.tipo) for d in docs}

    vencidos = [d for d in docs if st[d.id][0] == "vencido"]
    vencem_hoje = [d for d in docs if st[d.id][1] == 0]
    vencem_semana = [d for d in docs if st[d.id][1] is not None and 0 <= st[d.id][1] <= 7]
    processados_hoje = [d for d, dia in criados if dia == hoje]
    este_mes = [d for d, dia in criados if (dia.year, dia.month) == (hoje.year, hoje.month)]
    auto = sum(1 for d in docs if d.status_revisao == "auto_aprovado")

    semana = [dia for _, dia in criados if hoje - timedelta(days=6) <= dia <= hoje]
    semana_ant = [dia for _, dia in criados if hoje - timedelta(days=13) <= dia <= hoje - timedelta(days=7)]
    volume = _contagem_por_dia(semana, hoje - timedelta(days=6), 7)
    for v in volume:
        dia = date.fromisoformat(v["data"])
        v["rotulo"] = "Hoje" if dia == hoje else _DIAS_SEMANA[dia.weekday()]

    def setores(lista):
        return sorted({setor_do_tipo(d.tipo) for d in lista})

    atencao = []
    if vencidos:
        atencao.append({"tipo": "vencidos", "gravidade": "alta", "total": len(vencidos),
                        "titulo": f"{len(vencidos)} documento(s) vencido(s)", "subtitulo": " e ".join(setores(vencidos)),
                        "acao": "Ver", "rota": "/vencimentos?ate_dias=0"})
    if vencem_semana:
        atencao.append({"tipo": "vencem_semana", "gravidade": "alta" if vencem_hoje else "media",
                        "total": len(vencem_semana),
                        "titulo": (f"{len(vencem_hoje)} documento(s) vencem hoje" if vencem_hoje
                                   else f"{len(vencem_semana)} documento(s) vencem esta semana"),
                        "subtitulo": " e ".join(setores(vencem_semana)), "acao": "Ver",
                        "rota": "/vencimentos?ate_dias=7&incluir_vencidos=false"})
    if pendentes:
        altas = sum(1 for d in pendentes if d.prioridade == 3)
        atencao.append({"tipo": "revisao", "gravidade": "media", "total": len(pendentes),
                        "titulo": "Revisões pendentes", "subtitulo": f"{altas} documento(s) de alta prioridade",
                        "acao": "Revisar", "rota": "/revisao/fila"})
    irregulares = [t for t in db.scalars(select(Trabalhador))
                   if t.documentos and checklist.avaliar(t)["situacao"] == "irregular"]
    if irregulares:
        atencao.append({"tipo": "trabalhadores_irregulares", "gravidade": "alta", "total": len(irregulares),
                        "titulo": f"{len(irregulares)} trabalhador(es) com documentação irregular",
                        "subtitulo": "documento exigido faltando ou vencido", "acao": "Ver",
                        "rota": "/trabalhadores?situacao=irregular"})
    atencao.append({"tipo": "processados_hoje", "gravidade": "ok", "total": len(processados_hoje),
                    "titulo": f"{len(processados_hoje)} processado(s) hoje",
                    "subtitulo": "Todos os documentos classificados" if not pendentes
                    else f"{len(pendentes)} aguardando revisão", "acao": "Abrir", "rota": "/documentos"})

    por_setor = Counter(setor_do_tipo(d.tipo) for d in docs)
    recentes = sorted(docs, key=lambda d: d.criado_em or datetime.min, reverse=True)[:5]
    return {
        "hoje": hoje.isoformat(),
        "cartoes": {
            "documentos_ativos": {"valor": len(docs), "este_mes": len(este_mes)},
            "vencem_semana": {"valor": len(vencem_semana), "vencem_hoje": len(vencem_hoje), "vencidos": len(vencidos)},
            "aguardando_revisao": {"valor": len(pendentes),
                                   "alta_prioridade": sum(1 for d in pendentes if d.prioridade == 3)},
            "analisados_sem_revisao": {"percentual": _pct(auto, len(docs)), "total": auto},
        },
        "volume_7_dias": {"dias": volume, "total": len(semana),
                          "variacao_semana_anterior": _variacao(len(semana), len(semana_ant))},
        "atencao": atencao,
        "recentes": [doc_out(d).model_dump(mode="json") for d in recentes],
        "por_setor": [{"setor": s, "total": n, "percentual": _pct(n, len(docs))} for s, n in por_setor.most_common()],
        "fila_revisao": len(pendentes),
        "trabalhadores_irregulares": len(irregulares),
        "processados_hoje": len(processados_hoje),
    }


@router.get("/relatorios")
def relatorios(dias: int = 30, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    """Tela "Relatórios" para os últimos `dias` dias, comparando com o período anterior de mesmo tamanho."""
    dias = max(1, min(dias, 365))
    hoje = _hoje()
    inicio, inicio_ant = hoje - timedelta(days=dias - 1), hoje - timedelta(days=2 * dias - 1)
    todos = [(d, _local(d.criado_em).date()) for d in db.scalars(select(Documento))]
    periodo = [d for d, dia in todos if inicio <= dia <= hoje]
    anterior = [d for d, dia in todos if inicio_ant <= dia < inicio]

    auto = sum(1 for d in periodo if d.status_revisao == "auto_aprovado")
    auto_ant = sum(1 for d in anterior if d.status_revisao == "auto_aprovado")
    revisao = len(periodo) - auto

    # tempo de análise: do upload à conclusão do lote, dividido pelos documentos do lote
    tempos = []
    for lote, n in db.execute(select(Lote, func.count(Documento.id)).join(Documento, Documento.lote_id == Lote.id)
                              .where(Lote.status == "concluido").group_by(Lote.id)).all():
        if n and lote.criado_em and lote.atualizado_em and inicio <= _local(lote.criado_em).date() <= hoje:
            tempos.append((_local(lote.atualizado_em) - _local(lote.criado_em)).total_seconds() / n)
    tempo_medio = round(sum(tempos) / len(tempos), 1) if tempos else None

    prio = Counter(PRIORIDADE_NOME.get(d.prioridade, "media") for d in periodo)
    setor = Counter(setor_do_tipo(d.tipo) for d in periodo)
    prazos = _status_validade(periodo)
    com_prazo = prazos["vigente"] + prazos["vencendo"] + prazos["vencido"]
    return {
        "periodo": {"inicio": inicio.isoformat(), "fim": hoje.isoformat(), "dias": dias},
        "metricas": {
            "documentos_processados": {"valor": len(periodo), "variacao": _variacao(len(periodo), len(anterior))},
            "tempo_medio_analise_segundos": tempo_medio,
            "concluidos_sem_revisao": {"percentual": _pct(auto, len(periodo)),
                                       "variacao_pontos": (round(_pct(auto, len(periodo)) - _pct(auto_ant, len(anterior)), 1)
                                                           if anterior else None)},
            "enviados_para_revisao": {"valor": revisao},
        },
        "por_prioridade": [{"prioridade": p, "total": prio.get(p, 0), "percentual": _pct(prio.get(p, 0), len(periodo))}
                           for p in ("alta", "media", "baixa")],
        "por_setor": [{"setor": s, "total": n, "percentual": _pct(n, len(periodo))} for s, n in setor.most_common()],
        "status_prazos": [{"status": s, "rotulo": r, "total": prazos.get(s, 0), "percentual": _pct(prazos.get(s, 0), com_prazo)}
                          for s, r in (("vigente", "No prazo"), ("vencendo", "Vencem em breve"), ("vencido", "Vencidos"))],
        "volume_diario": _contagem_por_dia([dia for _, dia in todos if inicio <= dia <= hoje], inicio, dias),
    }
