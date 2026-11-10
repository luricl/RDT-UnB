#!/usr/bin/env python3
"""Calcula as métricas do relatório (Tabela 2) a partir de CSVs de métricas.

Uso: python3 results/entrega01/graph_scripts/calc_metrics.py <metrics.csv> [...]
Aceita um ou mais CSVs; com vários, imprime também uma tabela comparativa.

Definições:
  teórico = segment_size * 8 / RTT_médio            (Eq. 1; RTT = média de rtt_ms)
  medido  = total de bytes * 8 / tempo total        (1º REQ até o último DATA)
O CSV não guarda o instante do 1º REQ; ele é recuperado do 1º segmento:
  t_REQ0 = timestamp_0 - elapsed_0, com elapsed_0 = size_bytes * 8 / throughput_kbps.
"""
import csv
import statistics
import sys
from datetime import datetime
from pathlib import Path


def load(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("CSV sem segmentos")
    return rows


def compute(rows):
    size = [int(r["size_bytes"]) for r in rows]
    rtt = [float(r["rtt_ms"]) for r in rows if r["rtt_ms"]]
    thr = [float(r["throughput_kbps"]) for r in rows]
    total_bytes = sum(size)
    rtt_mean = statistics.fmean(rtt)

    t_last = datetime.fromisoformat(rows[-1]["timestamp"])
    t_first = datetime.fromisoformat(rows[0]["timestamp"])
    elapsed0_s = size[0] * 8 / thr[0] / 1000 if thr[0] > 0 else 0.0
    total_s = (t_last - t_first).total_seconds() + elapsed0_s

    # teórico = segment_size * 8 / RTT_médio
    # medido  = total de bytes * 8 / tempo total
    measured = total_bytes * 8 / total_s / 1000
    theoretical = statistics.fmean(size) * 8 / rtt_mean

    return {
        "protocol": rows[0].get("protocol", "?"),
        "segments": len(rows),
        "bytes": total_bytes,
        "rtt_mean": rtt_mean,
        "rtt_median": statistics.median(rtt),
        "rtt_min": min(rtt),
        "rtt_max": max(rtt),
        "theoretical": theoretical,
        "measured": measured,
        "ratio": measured / theoretical * 100,
        "retrans": sum(int(r["retransmissions"]) for r in rows),
        "timeouts": sum(int(r["timeout_occurred"]) for r in rows),
        "total_s": total_s,
        "thr_mean": statistics.fmean(thr),
        "thr_median": statistics.median(thr),
    }


def fmt(m):
    return "\n".join([
        f"protocolo:                 {m['protocol']}",
        f"segmentos / bytes:         {m['segments']} / {m['bytes']}",
        f"RTT médio (ms):            {m['rtt_mean']:.2f}",
        f"RTT mediana/mín/máx (ms):  {m['rtt_median']:.2f} / {m['rtt_min']:.2f} / {m['rtt_max']:.2f}",
        f"Throughput teórico (kbps): {m['theoretical']:.1f}",
        f"Throughput medido (kbps):  {m['measured']:.1f}",
        f"Medido/teórico (%):        {m['ratio']:.1f}",
        f"Retransmissões:            {m['retrans']}",
        f"Timeouts:                  {m['timeouts']}",
        f"Tempo total (s):           {m['total_s']:.1f}",
        f"Throughput inst. méd./med. (kbps): {m['thr_mean']:.1f} / {m['thr_median']:.1f}",
    ])


def main(paths):
    results = []
    for p in paths:
        m = compute(load(p))
        results.append((Path(p).name, m))
        print(f"== {Path(p).name}\n{fmt(m)}\n")
    if len(results) > 1:
        print(f"{'arquivo':<42}{'RTT(ms)':>8}{'teór.':>8}{'med.':>8}{'%':>7}{'retr.':>6}{'t(s)':>8}")
        for name, m in results:
            print(f"{name:<42}{m['rtt_mean']:>8.2f}{m['theoretical']:>8.1f}"
                  f"{m['measured']:>8.1f}{m['ratio']:>7.1f}{m['retrans']:>6}{m['total_s']:>8.1f}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
