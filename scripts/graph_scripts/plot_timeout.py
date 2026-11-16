#!/usr/bin/env python3
"""Gera os gráficos do timeout adaptativo do relatório final.

Uso: python3 scripts/graph_scripts/plot_timeout.py <metrics.csv> <pasta_saida> [inicio fim]

- rtt_estimado_vs_medido.png: RTT medido e RTT estimado (EWMA) na
  transferência inteira (em cima) e nos primeiros ZOOM_INICIO segmentos
  (embaixo), onde o estimador parte da primeira amostra.
- timeout_adaptativo.png: RTT medido, RTT estimado e timeout do REQ original
  num trecho [inicio, fim) da transferência; triângulos marcam os segmentos
  cujo timer venceu.

Os segmentos ficam em ordem de chegada (timestamp), que é a ordem em que o
estimador foi atualizado.
"""
import csv
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BLUE, ORANGE = "#2a6fbb", "#c4561a"
INK, MUTED, GRID = "#222222", "#666666", "#e3e3e3"
ZOOM_INICIO = 200
ZOOM = (6000, 6300)


def load(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: datetime.fromisoformat(r["timestamp"]))

    def col(name):
        return np.array([float(r[name]) if r[name] else np.nan for r in rows])

    retx = np.array([int(r["retransmissions"]) for r in rows])
    return {
        "rtt": col("rtt_ms"),
        "est": col("rtt_estimated_ms"),
        # O CSV guarda o timer já dobrado pelo backoff; desfaz para obter o
        # timeout com que o REQ original saiu.
        "timeout": col("timeout_ms") / 2.0 ** retx,
        "to": retx > 0,
    }


def style(ax, ylabel="ms"):
    ax.set_ylabel(ylabel, color=MUTED)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0)


def plot_estimate(run, out):
    n = len(run["rtt"])
    x = np.arange(n)
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(11, 6.5))
    top.scatter(x, run["rtt"], s=2, color=ORANGE, alpha=0.25, linewidths=0,
                label="RTT medido (sem retransmissão)")
    top.plot(x, run["est"], color=BLUE, linewidth=1.2,
             label="RTT estimado (EWMA)")
    style(top)
    top.set_ylim(0, 100)
    top.set_title(f"Transferência inteira ({n} segmentos)", color=INK,
                  fontsize=10, loc="left")
    top.legend(frameon=False, fontsize=8, labelcolor=MUTED, loc="upper right",
               markerscale=4)

    k = ZOOM_INICIO
    bottom.plot(x[:k], run["rtt"][:k], "o", ms=3, color=ORANGE, alpha=0.7,
                label="RTT medido")
    bottom.plot(x[:k], run["est"][:k], color=BLUE, linewidth=2,
                label="RTT estimado (EWMA)")
    style(bottom)
    bottom.set_xlabel("Segmento (ordem de chegada)", color=MUTED)
    bottom.set_title(f"Primeiros {k} segmentos: o estimador parte da "
                     "primeira amostra", color=INK, fontsize=10, loc="left")
    bottom.legend(frameon=False, fontsize=8, labelcolor=MUTED,
                  loc="upper right")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(out)


def plot_timeout(run, lo, hi, out):
    x = np.arange(lo, hi)
    rtt, est, to = run["rtt"][lo:hi], run["est"][lo:hi], run["to"][lo:hi]
    first = run["timeout"][lo:hi]
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.scatter(x, rtt, s=10, color=ORANGE, alpha=0.6, linewidths=0,
               label="RTT medido (sem retransmissão)")
    ax.plot(x, est, color=BLUE, linewidth=2, label="RTT estimado (EWMA)")
    ax.step(x, first, where="mid", color=INK, linewidth=1.2,
            label="timeout = max(50, Est + 4·Dev)")
    ax.scatter(x[to], first[to], s=30, marker="v", color=INK, zorder=3,
               label=f"timer venceu ({to.sum()} no trecho)")
    style(ax)
    ax.set_xlabel("Segmento (ordem de chegada)", color=MUTED)
    ax.set_ylim(0, max(100, np.nanmax(first) * 1.1))
    ax.legend(frameon=False, fontsize=8, labelcolor=MUTED, loc="upper right",
              ncol=2, markerscale=1.5)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(out)


def main():
    if len(sys.argv) not in (3, 5):
        sys.exit(__doc__)
    run = load(sys.argv[1])
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    lo, hi = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) == 5 else ZOOM
    plot_estimate(run, out_dir / "rtt_estimado_vs_medido.png")
    plot_timeout(run, lo, hi, out_dir / "timeout_adaptativo.png")


if __name__ == "__main__":
    main()
