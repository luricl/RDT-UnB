#!/usr/bin/env python3
"""Compara pares (alpha, beta) reproduzindo offline o mesmo traço de RTT.

Na rede real, cada execução pega uma rede diferente (o RTT mediano variou de
26 a 93 ms numa mesma tarde), então comparar pares pelo tempo total mede mais
a rede do que o par. Aqui todos os pares recebem a mesma sequência de RTTs,
tirada de execuções com timeout fixo de 1000 ms (nenhuma amostra é cortada
por timeout). Para cada amostra, o timeout que estava valendo antes dela é
comparado com o RTT medido:

- timeouts_espurios: amostras maiores que o timeout (o timer teria vencido
  sem perda nenhuma);
- timeout_medio_ms: quanto cada perda real custaria, em média.

Além dos traços reais, o primeiro arquivo gera um traço sintético "pulso":
o mesmo RTT com +STEP_MS no terço do meio, como o "delay adicional" do
cenário surpresa ligado e depois desligado. Nele, colunas a mais medem a
reação do par:

- espurios_apos_subida: espúrios nas REACTION amostras seguintes à subida;
- amostras_ate_90pct: quantas amostras o EstimatedRTT leva para cobrir 90%
  da subida;
- timeout_apos_descida_ms: timeout médio nas REACTION amostras depois que o
  atraso some, ou seja, quanto uma perda custaria logo depois do pulso.

Uso: python3 scripts/ewma_replay.py <saida.csv> <metrics.csv> [<metrics.csv> ...]
"""
import csv
import os
import statistics
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.rtt import DEFAULT_MIN_TIMEOUT_MS, RttEstimator  # noqa: E402

PAIRS = [(0.125, 0.25), (0.05, 0.25), (0.25, 0.25), (0.5, 0.25),
         (0.125, 0.1), (0.125, 0.5), (1.0, 1.0)]
FLOORS = [0.0, DEFAULT_MIN_TIMEOUT_MS]
STEP_MS = 100.0
REACTION = 100


def load_trace(path):
    """RTTs sem retransmissão, em ordem de chegada (ordem de atualização)."""
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: datetime.fromisoformat(r["timestamp"]))
    return [float(r["rtt_ms"]) for r in rows
            if r["rtt_ms"] and r["retransmissions"] == "0"]


def replay(trace, alpha, beta, floor, pulse=None):
    """`pulse` = (início, fim) do trecho com +STEP_MS, só no traço sintético."""
    est = RttEstimator(alpha=alpha, beta=beta, min_timeout_ms=floor)
    est.update(trace[0])
    spurious, timeouts = 0, []
    after_rise, converged, after_drop = 0, None, []
    for i, sample in enumerate(trace[1:], start=1):
        timeout = est.timeout_ms(fallback_ms=None)
        timeouts.append(timeout)
        if sample > timeout:
            spurious += 1
            if pulse and pulse[0] <= i < pulse[0] + REACTION:
                after_rise += 1
        if pulse and pulse[1] <= i < pulse[1] + REACTION:
            after_drop.append(timeout)
        est.update(sample)
        if (pulse and i >= pulse[0] and converged is None
                and est.estimated_ms >= trace[pulse[0] - 1] + 0.9 * STEP_MS):
            converged = i - pulse[0] + 1
    result = {"timeouts_espurios": spurious,
              "espurios_pct": round(100 * spurious / (len(trace) - 1), 2),
              "timeout_medio_ms": round(statistics.fmean(timeouts), 1)}
    if pulse:
        result["espurios_apos_subida"] = after_rise
        result["amostras_ate_90pct"] = converged
        result["timeout_apos_descida_ms"] = round(statistics.fmean(after_drop), 1)
    return result


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    out, paths = sys.argv[1], sys.argv[2:]
    traces = [(os.path.relpath(p, ROOT).replace("\\", "/"), load_trace(p), None)
              for p in paths]
    name, first, _ = traces[0]
    a, b = len(first) // 3, 2 * len(first) // 3
    traces.append((f"pulso +{STEP_MS:g} ms em {name}",
                   first[:a] + [s + STEP_MS for s in first[a:b]] + first[b:],
                   (a, b)))

    rows = []
    for name, trace, pulse in traces:
        for floor in FLOORS:
            for alpha, beta in PAIRS:
                rows.append({
                    "traco": name,
                    "amostras": len(trace),
                    "rtt_mediano_ms": round(statistics.median(trace), 1),
                    "piso_ms": floor, "alpha": alpha, "beta": beta,
                    "espurios_apos_subida": "", "amostras_ate_90pct": "",
                    "timeout_apos_descida_ms": "",
                    **replay(trace, alpha, beta, floor, pulse),
                })
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(out)


if __name__ == "__main__":
    main()
