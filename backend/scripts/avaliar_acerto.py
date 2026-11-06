"""Mede o % de acerto do sistema num lote com gabarito — e serve de gate de qualidade no CI.

    python scripts/avaliar_acerto.py lote_terceiros.pdf [--gabarito X.gabarito.json] [--min-corte 90] [--min-tipo 90] [--sem-llm]

Roda o pipeline inteiro DENTRO deste processo, num banco e numa pasta temporários (não toca no banco de verdade):
sobe o PDF pela mesma rota de upload da API, processa com o worker, grava o gabarito e lê GET /lotes/{id}/avaliacao.
Sai com código 0 se corte_f1 >= --min-corte e tipo_acerto_pct >= --min-tipo; senão 1.
"""
import argparse
import json
import os
import sys
import tempfile


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pdf")
    ap.add_argument("--gabarito", help="padrão: mesmo nome do PDF com .gabarito.json")
    ap.add_argument("--min-corte", type=float, default=90.0)
    ap.add_argument("--min-tipo", type=float, default=90.0)
    ap.add_argument("--sem-llm", action="store_true", help="força LLM_PROVIDER=nenhum (só regras)")
    args = ap.parse_args()

    pdf = os.path.abspath(args.pdf)
    gab_path = args.gabarito or os.path.splitext(pdf)[0] + ".gabarito.json"
    with open(gab_path, encoding="utf-8") as f:
        gabarito = json.load(f)

    # ANTES de importar app.*: as configurações são lidas no import (mesmo padrão de tests/conftest.py)
    tmp = tempfile.mkdtemp(prefix="avaliar_acerto_")
    os.environ.update(DATABASE_URL=f"sqlite:///{tmp}/avaliacao.db", DATA_DIR=tmp, AUTH_ATIVO="false",
                      API_KEY="", WORKER_INLINE="false", STORAGE_BACKEND="local")
    if args.sem_llm:
        os.environ["LLM_PROVIDER"] = "nenhum"
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from fastapi.testclient import TestClient

    from app import worker
    from app.main import app

    with TestClient(app) as c:
        with open(pdf, "rb") as f:
            r = c.post("/lotes", files={"arquivo": (os.path.basename(pdf), f, "application/pdf")})
        r.raise_for_status()
        lote_id = r.json()["id"]
        worker.rodar(uma_vez=True)
        r = c.put(f"/lotes/{lote_id}/gabarito", json=gabarito)
        if r.status_code != 200:
            print(f"gabarito recusado: {r.text}")
            return 1
        r = c.get(f"/lotes/{lote_id}/avaliacao")
        if r.status_code != 200:
            print(f"avaliação indisponível: {r.text}")
            return 1
        m = r.json()["metricas"]

    def fmt(v):
        return "—" if v is None else f"{v:.1f}%"

    print(f"\nAcerto em {os.path.basename(pdf)} ({m['totais']['gabarito']} documentos no gabarito, "
          f"{m['totais']['previstos']} previstos)")
    for rotulo, chave in [("Cortes — precisão", "corte_precisao"), ("Cortes — revocação", "corte_revocacao"),
                          ("Cortes — F1", "corte_f1"), ("Documentos exatos", "documentos_exatos_pct"),
                          ("Tipo certo (docs exatos)", "tipo_acerto_pct"),
                          ("Tipo certo (por página)", "tipo_acerto_por_pagina_pct"),
                          ("Aprovados sem revisão", "automatizados_pct"),
                          ("Acerto dos aprovados sem revisão", "acerto_dos_automatizados_pct")]:
        print(f"  {rotulo:<34} {fmt(m[chave]):>7}")
    print(f"  {'Erros silenciosos':<34} {len(m['erros_silenciosos']):>7}")
    for d in m["detalhes"]:
        print(f"  · {d}")

    ok = (m["corte_f1"] or 0) >= args.min_corte and (m["tipo_acerto_pct"] or 0) >= args.min_tipo
    print("\nOK" if ok else f"\nABAIXO DO MÍNIMO (corte ≥ {args.min_corte}, tipo ≥ {args.min_tipo})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
