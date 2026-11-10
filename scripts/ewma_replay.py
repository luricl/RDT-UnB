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

Além dos traços reais, o primeiro arquivo gera um traço sintético "degrau":
o mesmo RTT com +STEP_MS a partir da metade, como o "delay adicional" do
cenário surpresa. Nele, duas colunas a mais medem a reação do par:

- espurios_apos_degrau: espúrios nas REACTION amostras seguintes ao degrau;
- amostras_ate_90pct: quantas amostras o EstimatedRTT leva para cobrir 90%
  do degrau.

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
REACTION = 50


def load_trace(path):
    """RTTs sem retransmissão, em ordem de chegada (ordem de atualização)."""
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: datetime.fromisoformat(r["timestamp"]))
    return [float(r["rtt_ms"]) for r in rows
            if r["rtt_ms"] and r["retransmissions"] == "0"]


def replay(trace, alpha, beta, floor, step_at=None):
    est = RttEstimator(alpha=alpha, beta=beta, min_timeout_ms=floor)
    est.update(trace[0])
    spurious, timeouts = 0, []
    after_step, converged = 0, None
    for i, sample in enumerate(trace[1:], start=1):
        timeout = est.timeout_ms(fallback_ms=None)
        timeouts.append(timeout)
        if sample > timeout:
            spurious += 1
            if step_at is not None and step_at <= i < step_at + REACTION:
                after_step += 1
        est.update(sample)
        if (step_at is not None and i >= step_at and converged is None
                and est.estimated_ms >= trace[step_at - 1] + 0.9 * STEP_MS):
            converged = i - step_at + 1
    result = {"timeouts_espurios": spurious,
              "espurios_pct": round(100 * spurious / (len(trace) - 1), 2),
              "timeout_medio_ms": round(statistics.fmean(timeouts), 1)}
    if step_at is not None:
        result["espurios_apos_degrau"] = after_step
        result["amostras_ate_90pct"] = converged
    return result


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    out, paths = sys.argv[1], sys.argv[2:]
    traces = [(os.path.relpath(p, ROOT).replace("\\", "/"), load_trace(p), None)
              for p in paths]
    name, first, _ = traces[0]
    half = len(first) // 2
    traces.append((f"degrau +{STEP_MS:g} ms em {name}",
                   first[:half] + [s + STEP_MS for s in first[half:]], half))

    rows = []
    for name, trace, step_at in traces:
        for floor in FLOORS:
            for alpha, beta in PAIRS:
                rows.append({
                    "traco": name,
                    "amostras": len(trace),
                    "rtt_mediano_ms": round(statistics.median(trace), 1),
                    "piso_ms": floor, "alpha": alpha, "beta": beta,
                    "espurios_apos_degrau": "", "amostras_ate_90pct": "",
                    **replay(trace, alpha, beta, floor, step_at),
                })
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(out)


if __name__ == "__main__":
    main()
