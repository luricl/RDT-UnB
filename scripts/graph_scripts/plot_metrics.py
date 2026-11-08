#!/usr/bin/env python3
"""Gera o gráfico de throughput e RTT por segmento de um CSV de métricas.

Uso: python3 results/entrega01/graph_scripts/plot_metrics.py <metrics.csv>
Salva um PNG com o mesmo nome do CSV, na mesma pasta.
"""
import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BLUE, ORANGE = "#2a6fbb", "#c4561a"
INK, MUTED, GRID = "#222222", "#666666", "#e3e3e3"


def load(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    seg = np.array([int(r["segment"]) for r in rows])
    rtt = np.array([float(r["rtt_ms"]) if r["rtt_ms"] else np.nan for r in rows])
    thr = np.array([float(r["throughput_kbps"]) for r in rows])
    to = np.array([int(r["timeout_occurred"]) for r in rows], dtype=bool)
    return seg, rtt, thr, to


def moving_avg(y, w):
    w = max(1, min(w, len(y)))
    return np.convolve(y, np.ones(w) / w, mode="valid")


def style(ax, ylabel):
    ax.set_ylabel(ylabel, color=MUTED)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0)


def panel(ax, seg, y, color, ylabel, label, to=None):
    w = max(1, len(y) // 50)
    ax.plot(seg, y, color=color, alpha=0.3, linewidth=0.6, label=label)
    ax.plot(seg[w - 1:], moving_avg(y, w), color=color, linewidth=2,
            label=f"média móvel ({w} seg.)")
    ax.axhline(y.mean(), color=INK, linewidth=1, linestyle=(0, (4, 3)),
               label=f"média global ({y.mean():.1f})")
    if to is not None and to.any():
        ax.scatter(seg[to], y[to], s=40, color=INK, zorder=3, label="timeout")
    style(ax, ylabel)
    ax.legend(frameon=False, fontsize=8, labelcolor=MUTED, loc="upper right",
              ncol=4)


def plot(csv_path):
    seg, rtt, thr, to = load(csv_path)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    panel(a1, seg, thr, BLUE, "Throughput (kbps)", "por segmento")
    panel(a2, seg, rtt, ORANGE, "RTT (ms)", "por segmento", to)
    a2.set_xlabel("Segmento", color=MUTED)
    fig.suptitle(f"{csv_path.stem} — {len(seg)} segmentos, "
                 f"{to.sum()} timeout(s)", color=INK, fontsize=12, x=0.01,
                 ha="left")
    fig.tight_layout()
    out = csv_path.with_suffix(".png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(out)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    path = Path(sys.argv[1])
    if not path.is_file():
        sys.exit(f"CSV não encontrado: {path}")
    plot(path)


main()
