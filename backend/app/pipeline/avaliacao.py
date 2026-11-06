"""Quanto o sistema acerta? Compara a separação/classificação com um GABARITO (verdade conhecida).

Função pura, sem banco: recebe o gabarito e o que o sistema previu e devolve as métricas que a banca pergunta
(cortes, documentos exatos, tipo) e, principalmente, os ERROS SILENCIOSOS: documentos aprovados
automaticamente que estão errados — é o número que mede o risco real da automação.
Páginas 0-based; página fora de todo documento do gabarito é separador (ex.: página em branco).
"""
from app.status import StatusRevisao
from app.tipos import TIPOS, nome_tipo


def _pct(parte: int, total: int) -> float | None:
    return round(100 * parte / total, 1) if total else None


def _fronteiras(docs: list[dict]) -> set[int]:
    return {min(d["paginas"]) for d in docs if d["paginas"]}


def _faixa(paginas: list[int]) -> str:
    a, b = min(paginas) + 1, max(paginas) + 1          # na tela as páginas são contadas a partir de 1
    return f"pág {a}" if a == b else f"págs {a}–{b}"


def _rotulo(d: dict) -> str:
    return f"{d['tipo']} {_faixa(d['paginas'])}"


def validar_gabarito(gab: dict, total_paginas: int) -> list[dict]:
    """Confere o JSON do gabarito; devolve a lista de documentos ou levanta ValueError com mensagem clara."""
    docs = gab.get("documentos") if isinstance(gab, dict) else None
    if not isinstance(docs, list) or not docs:
        raise ValueError("o gabarito precisa de 'documentos': lista com pelo menos um item")
    vistas: set[int] = set()
    for i, d in enumerate(docs, 1):
        if not isinstance(d, dict) or not isinstance(d.get("paginas"), list) or not d["paginas"]:
            raise ValueError(f"documento {i}: 'paginas' deve ser uma lista não vazia")
        if d.get("tipo") not in TIPOS:
            raise ValueError(f"documento {i}: tipo '{d.get('tipo')}' não existe (veja GET /tipos)")
        for p in d["paginas"]:
            if not isinstance(p, int) or isinstance(p, bool) or not 0 <= p < total_paginas:
                raise ValueError(f"documento {i}: página {p} fora do lote (0 a {total_paginas - 1})")
            if p in vistas:
                raise ValueError(f"página {p} aparece em mais de um documento")
            vistas.add(p)
    return [{"tipo": d["tipo"], "paginas": sorted(d["paginas"])} for d in docs]


def comparar(gabarito: list[dict], previstos: list[dict]) -> dict:
    """previstos: [{"tipo", "paginas", "status_revisao", "id"}]."""
    G, P = _fronteiras(gabarito), _fronteiras(previstos)
    acertos = len(G & P)
    prec, rev = _pct(acertos, len(P)), _pct(acertos, len(G))
    f1 = round(2 * prec * rev / (prec + rev), 1) if prec and rev else (0.0 if prec is not None and rev is not None else None)

    por_conjunto = {frozenset(g["paginas"]): g for g in gabarito}
    exatos = [(p, por_conjunto[frozenset(p["paginas"])]) for p in previstos if frozenset(p["paginas"]) in por_conjunto]
    tipo_certo = sum(1 for p, g in exatos if p["tipo"] == g["tipo"])

    tipo_previsto_da_pagina = {n: p["tipo"] for p in previstos for n in p["paginas"]}
    paginas_gab = [(n, g["tipo"]) for g in gabarito for n in g["paginas"]]
    paginas_tipo_ok = sum(1 for n, t in paginas_gab if tipo_previsto_da_pagina.get(n) == t)

    ok_ids = {p["id"] for p, g in exatos if p["tipo"] == g["tipo"]}
    auto = [p for p in previstos if p.get("status_revisao") == StatusRevisao.AUTO_APROVADO]
    silenciosos = [{"id": p["id"], "tipo_previsto": p["tipo"], "paginas": p["paginas"]}
                   for p in auto if p["id"] not in ok_ids]

    return {
        "totais": {"gabarito": len(gabarito), "previstos": len(previstos)},
        "corte_precisao": prec, "corte_revocacao": rev, "corte_f1": f1,
        "documentos_exatos_pct": _pct(len(exatos), len(gabarito)),
        "tipo_acerto_pct": _pct(tipo_certo, len(exatos)),
        "tipo_acerto_por_pagina_pct": _pct(paginas_tipo_ok, len(paginas_gab)),
        "automatizados_pct": _pct(len(auto), len(previstos)),
        "acerto_dos_automatizados_pct": _pct(len(auto) - len(silenciosos), len(auto)),
        "erros_silenciosos": silenciosos,
        "detalhes": _divergencias(gabarito, previstos),
    }


def _divergencias(gabarito: list[dict], previstos: list[dict]) -> list[str]:
    """Frases legíveis: 'gabarito: CONTRATO págs 12–13 · sistema: CONTRATO pág 12 + DESCONHECIDO pág 13'."""
    previstos_por_conjunto = {frozenset(p["paginas"]): p for p in previstos}
    detalhes, explicados = [], set()
    for g in gabarito:
        p = previstos_por_conjunto.get(frozenset(g["paginas"]))
        if p:
            explicados.add(p["id"])
            if p["tipo"] != g["tipo"]:
                detalhes.append(f"gabarito: {_rotulo(g)} · sistema: {_rotulo(p)} (tipo errado: "
                                f"{nome_tipo(p['tipo'])} no lugar de {nome_tipo(g['tipo'])})")
            continue
        cobrem = [q for q in previstos if set(q["paginas"]) & set(g["paginas"])]
        explicados.update(q["id"] for q in cobrem)
        sistema = " + ".join(_rotulo(q) for q in cobrem) or "nenhum documento"
        detalhes.append(f"gabarito: {_rotulo(g)} · sistema: {sistema}")
    for q in previstos:
        if q["id"] not in explicados:
            detalhes.append(f"sistema criou {_rotulo(q)}, que no gabarito é só separador")
    return detalhes
