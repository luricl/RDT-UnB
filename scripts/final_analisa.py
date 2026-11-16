#!/usr/bin/env python3
"""Resume a campanha de scripts/final_executa.py.

Lê results/final/execucoes.csv e grava:

    results/final/resumo.csv   uma linha por cenário, com as métricas do CSV
    results/final/replay.csv   pares alfa/beta reproduzidos sobre o traço de
                               RTT da execução sr_fixo_p00 (ver ewma_replay.py)

Colunas do resumo:
    tempo_s, vazao_kbps   do 1º REQ ao último DATA (summarize_metrics)
    retransmissoes        REQs reenviados
    perdas_simuladas      segmentos com algum DATA descartado pelo cliente
    desnecessarias        retransmissões cujo DATA original chegou depois
                          (DATA duplicado; só SR)
    rtt_mediano_ms        mediana do rtt_ms (segmentos sem retransmissão)
    timeout_medio_ms      média do timeout do REQ original de cada segmento

Uso: python3 scripts/final_analisa.py
"""
import csv
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from src.metrics import summarize_metrics  # noqa: E402
import ewma_replay  # noqa: E402

OUT = os.path.join(ROOT, "results", "final")


def manifest():
    with open(os.path.join(OUT, "execucoes.csv"), newline="",
              encoding="utf-8") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def summary(run):
    path = os.path.join(ROOT, run["csv"])
    s = summarize_metrics(path)
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rtts = [float(r["rtt_ms"]) for r in rows if r["rtt_ms"]]
    # O CSV guarda o timer já dobrado pelo backoff nos retransmitidos.
    first_timeouts = [float(r["timeout_ms"]) / 2 ** int(r["retransmissions"])
                      if run["adaptativo"] == "1" else float(r["timeout_ms"])
                      for r in rows]
    return {
        "id": run["id"], "protocolo": run["protocolo"], "janela": run["janela"],
        "arquivo": run["arquivo"], "perda": run["perda"],
        "adaptativo": run["adaptativo"], "piso_ms": run["piso_ms"],
        "alpha": run["alpha"], "beta": run["beta"],
        "segmentos": s["segments"],
        "tempo_s": round(s["duration_s"], 1),
        "vazao_kbps": round(s["throughput_kbps"], 1),
        "retransmissoes": s["retransmissions"],
        "perdas_simuladas": s["loss_simulated"],
        "desnecessarias": run["desnecessarias"],
        "rtt_mediano_ms": round(statistics.median(rtts), 1),
        "timeout_medio_ms": round(statistics.fmean(first_timeouts), 1),
        "md5": run["md5"], "done_ok": run["done_ok"], "inicio": run["inicio"],
        "csv": os.path.basename(run["csv"]),
    }


def write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        fields = list(dict.fromkeys(k for r in rows for k in r))
        w = csv.DictWriter(f, fieldnames=fields, restval="")
        w.writeheader()
        w.writerows(rows)
    print(os.path.relpath(path, ROOT))


def main():
    runs = manifest()
    rows = [summary(r) for r in runs.values()]
    write(os.path.join(OUT, "resumo.csv"), rows)
    if "sr_fixo_p00" in runs:
        trace = ewma_replay.load_trace(os.path.join(ROOT, runs["sr_fixo_p00"]["csv"]))
        a, b = len(trace) // 3, 2 * len(trace) // 3
        pulse = trace[:a] + [x + ewma_replay.STEP_MS for x in trace[a:b]] + trace[b:]
        out = []
        for name, tr, p in (("estavel", trace, None), ("degrau", pulse, (a, b))):
            for floor in ewma_replay.FLOORS:
                for alpha, beta in ewma_replay.PAIRS:
                    out.append({"traco": name, "piso_ms": floor, "alpha": alpha,
                                "beta": beta,
                                **ewma_replay.replay(tr, alpha, beta, floor, p)})
        write(os.path.join(OUT, "replay.csv"), out)


if __name__ == "__main__":
    main()
