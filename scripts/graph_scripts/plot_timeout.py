#!/usr/bin/env python3
"""Gera os gráficos do timeout adaptativo da Entrega 3.

Uso: python3 scripts/graph_scripts/plot_timeout.py <sem_piso.csv> <com_piso.csv> <pasta_saida>

- rtt_estimado_vs_medido.png: RTT medido, RTT estimado e timeout do REQ
  original num trecho de ZOOM_EST segmentos da execução com piso.
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
ZOOM_EST = (10200, 10850)  # trecho do RTT estimado: picos do DevRTT e a rajada de timeouts


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
    lo, hi = ZOOM_EST
    x = np.arange(lo, hi)
    rtt, est, to = run["rtt"][lo:hi], run["est"][lo:hi], run["to"][lo:hi]
    # O CSV guarda o timer já dobrado pelo backoff; desfaz para mostrar o
    # timeout com que o REQ original saiu (o que de fato venceu).
    first = run["timeout"][lo:hi] / 2.0 ** run["retx"][lo:hi]

    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.scatter(x, rtt, s=8, color=ORANGE, alpha=0.5, linewidths=0,
               label="RTT medido (sem retransmissão)")
    ax.plot(x, est, color=BLUE, linewidth=2, label="RTT estimado (EWMA)")
    ax.step(x, first, where="mid", color=INK, linewidth=1.2,
            label="timeout = max(50, Est + 4·Dev)")
    ax.scatter(x[to], first[to], s=40, marker="v", color=INK, zorder=3,
               label="REQ cujo timer venceu")
    style(ax, "ms")
    ax.set_ylim(0, 80)
    ax.set_title(f"Segmentos {lo} a {hi} de {len(run['rtt'])} (piso de 50 ms, "
                 "sem perda): o timeout só sai do piso quando o RTT oscila",
                 color=INK, fontsize=10, loc="left")
    if to.any():
        i = x[to]
        ax.annotate(f"{to.sum()} REQs da janela venceram juntos:\n"
                    "a rede segurou os DATA por mais de 50 ms\n"
                    "(sem RTT medido: Karn descarta a amostra)",
                    xy=(i.mean(), 50), xytext=(i.mean() - 230, 64),
                    fontsize=8, color=MUTED,
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
    ax.legend(frameon=False, fontsize=8, labelcolor=MUTED, loc="lower right",
              ncol=4, markerscale=1.5)
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
