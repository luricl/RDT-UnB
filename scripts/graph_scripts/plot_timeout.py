#!/usr/bin/env python3
"""Gera os gráficos do timeout adaptativo da Entrega 3.

Uso: python3 scripts/graph_scripts/plot_timeout.py <sem_piso.csv> <com_piso.csv> <pasta_saida>

- rtt_estimado_vs_medido.png: RTT medido, RTT estimado e timeout aplicado
  na execução com piso.
- timeout_adaptativo.png: lado a lado, sem piso e com piso, o timeout do
  primeiro REQ de cada segmento sobre o RTT medido, num trecho de ZOOM
  segmentos; os triângulos marcam os segmentos que estouraram o timer.

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
ZOOM = (5000, 5500)  # trecho do gráfico lado a lado (ordem de chegada)


def load(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: datetime.fromisoformat(r["timestamp"]))

    def col(name):
        return np.array([float(r[name]) if r[name] else np.nan for r in rows])

    return {
        "rtt": col("rtt_ms"),
        "est": col("rtt_estimated_ms"),
        "timeout": col("timeout_ms"),
        "to": np.array([int(r["timeout_occurred"]) for r in rows], dtype=bool),
        "retx": np.array([int(r["retransmissions"]) for r in rows]),
    }


def style(ax, ylabel):
    ax.set_ylabel(ylabel, color=MUTED)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0)
    ax.set_xlabel("Segmento (ordem de chegada)", color=MUTED)


def plot_estimate(run, out):
    x = np.arange(len(run["rtt"]))
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.scatter(x, run["rtt"], s=2, color=ORANGE, alpha=0.35, linewidths=0,
               label="RTT medido (sem retransmissão)")
    ax.plot(x, run["est"], color=BLUE, linewidth=2, label="RTT estimado (EWMA)")
    ax.plot(x, run["timeout"], color=INK, linewidth=1,
            linestyle=(0, (4, 3)), label="timeout aplicado")
    if run["to"].any():
        ax.scatter(x[run["to"]], run["timeout"][run["to"]], s=30, marker="v",
                   color=INK, zorder=3, label=f"timeout ({run['to'].sum()})")
    style(ax, "ms")
    # A primeira janela sai com o timeout inicial (--timeout), antes de
    # qualquer amostra; ela fica fora da escala para não achatar o resto.
    t = run["timeout"]
    ax.set_ylim(0, np.nanmax(t[t < t[0]]) * 1.15)
    ax.annotate(f"1ª janela: timeout inicial de {t[0]:.0f} ms (fora da escala)",
                xy=(0, ax.get_ylim()[1]), xytext=(8, -12),
                textcoords="offset points", fontsize=8, color=MUTED)
    ax.legend(frameon=False, fontsize=8, labelcolor=MUTED, loc="lower right",
              ncol=4, markerscale=3)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(out)


def plot_timeouts(no_floor, floor, out):
    lo, hi = ZOOM
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    for ax, run, color, title in ((axes[0], no_floor, ORANGE, "sem piso"),
                                  (axes[1], floor, BLUE, "com piso de 50 ms")):
        x = np.arange(lo, hi)
        rtt, to = run["rtt"][lo:hi], run["to"][lo:hi]
        # Num segmento retransmitido o CSV guarda o timer já dobrado (backoff);
        # aqui interessa o timeout com que o REQ original saiu.
        first = np.where(run["retx"][lo:hi] == 0, run["timeout"][lo:hi], np.nan)
        ax.scatter(x, rtt, s=6, color=MUTED, alpha=0.5, linewidths=0,
                   label="RTT medido")
        ax.plot(x, first, color=color, linewidth=1.5,
                label="timeout do REQ original")
        ax.scatter(x[to], np.full(to.sum(), 5), s=30, marker="v", color=INK,
                   label=f"segmento com timeout ({to.sum()} no trecho)")
        style(ax, "ms")
        ax.set_title(f"{title}: {run['to'].sum()} timeouts em "
                     f"{len(run['to'])} segmentos", color=INK, fontsize=10,
                     loc="left")
        ax.legend(frameon=False, fontsize=8, labelcolor=MUTED,
                  loc="upper right", markerscale=2)
    axes[0].set_ylim(0, 80)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(out)


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    no_floor, floor = load(sys.argv[1]), load(sys.argv[2])
    out_dir = Path(sys.argv[3])
    out_dir.mkdir(parents=True, exist_ok=True)
    plot_estimate(floor, out_dir / "rtt_estimado_vs_medido.png")
    plot_timeouts(no_floor, floor, out_dir / "timeout_adaptativo.png")


if __name__ == "__main__":
    main()
