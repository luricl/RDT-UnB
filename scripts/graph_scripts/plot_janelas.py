#!/usr/bin/env python3
"""Gera o gráfico de throughput em janelas de 10 s de um CSV de métricas.

Uso: python3 results/entrega01/graph_scripts/plot_janelas.py <metrics.csv>
Salva <nome_do_csv>_janelas_10s.png na mesma pasta do CSV.
"""
import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

WINDOW_S = 10
BLUE = "#2a6fbb"
INK, MUTED, GRID = "#222222", "#666666", "#e3e3e3"
# Fuso dos timestamps dos CSVs (Brasília).
BRT = timezone(timedelta(hours=-3))


def mpl_time(seconds):
    """Converte segundos Unix para o eixo de datas do matplotlib (horário de Brasília)."""
    seconds = np.atleast_1d(seconds)
    return mdates.date2num([datetime.fromtimestamp(x, BRT).replace(tzinfo=None)
                            for x in seconds])


def load(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    t = np.array([datetime.fromisoformat(r["timestamp"]).timestamp() for r in rows])
    size = np.array([int(r["size_bytes"]) for r in rows], dtype=float)
    to = np.array([int(r["timeout_occurred"]) for r in rows], dtype=bool)
    return t, size, to


def windows(t, size):
    """Soma os bytes que chegam em cada janela de WINDOW_S e converte em kbit/s."""
    start = np.floor(t[0] / WINDOW_S) * WINDOW_S
    idx = np.floor((t - start) / WINDOW_S).astype(int)
    total = np.bincount(idx, weights=size)
    centers = start + (np.arange(len(total)) + 0.5) * WINDOW_S
    return mpl_time(centers), total * 8 / WINDOW_S / 1000


def style(ax):
    ax.set_ylabel("Throughput (kbps)", color=MUTED)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0)


def plot(path):
    t, size, to = load(path)
    day = datetime.fromtimestamp(t[0], BRT).date()
    c, thr = windows(t, size)
    fig, ax = plt.subplots(figsize=(11, 4.6))
    ax.plot(c, thr, color=BLUE, linewidth=1.8, marker="o", markersize=3,
            label=f"{path.stem} ({len(t)} segmentos)")
    if to.any():
        ax.scatter(mpl_time(t[to]), np.full(to.sum(), thr.max() * 0.03),
                   marker="v", s=36, color=INK, zorder=3, label="timeout")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.set_xlabel(f"Horário ({day:%d/%m/%Y}, relógio do sistema)", color=MUTED)
    ax.set_ylim(0, thr.max() * 1.1)
    style(ax)
    ax.legend(frameon=False, fontsize=8, labelcolor=MUTED, loc="lower left",
              ncol=4)
    ax.set_title(f"Throughput em janelas de {WINDOW_S} s", color=INK,
                 fontsize=11, loc="left")
    fig.tight_layout()
    out = path.with_name(f"{path.stem}_janelas_{WINDOW_S}s.png")
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
