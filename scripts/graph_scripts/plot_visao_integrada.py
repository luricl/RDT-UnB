#!/usr/bin/env python3
"""Gera o gráfico da visão integrada (throughput médio, arquivo large, sem perda).

Uso: python3 scripts/graph_scripts/plot_visao_integrada.py <saida.png>

Uma barra por linha da tabela consolidada do relatório final, todas da
campanha em results/final (execucoes.csv). O throughput é recalculado do CSV
de cada execução (summarize_metrics).
"""
import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.metrics import summarize_metrics  # noqa: E402

GREEN, BLUE, ORANGE = "#1a9e77", "#2a6fbb", "#c4561a"   # SAW, GBN, SR
INK, MUTED, GRID = "#222222", "#666666", "#e3e3e3"

# (rótulo, cor, adaptativo, id da execução em results/final/execucoes.csv)
BARS = [
    ("SAW\nfixo 1 s", GREEN, False, "saw_large_p00"),
    ("GBN (N=16)\nfixo 1 s", BLUE, False, "gbn_fixo_p00"),
    ("SR (N=16)\nfixo 1 s", ORANGE, False, "sr_fixo_p00"),
    ("SR (N=16)\nadaptativo", ORANGE, True, "sr_adapt_p00"),
]


def throughput(run_id):
    with open(ROOT / "results/final/execucoes.csv", newline="",
              encoding="utf-8") as f:
        runs = {r["id"]: r for r in csv.DictReader(f)}
    return summarize_metrics(str(ROOT / runs[run_id]["csv"]))["throughput_kbps"]


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    out = Path(sys.argv[1])
    values = [throughput(src) for *_, src in BARS]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = range(len(BARS))
    for i, ((label, color, adaptive, _), v) in enumerate(zip(BARS, values)):
        ax.bar(i, v, width=0.68, color="white" if adaptive else color,
               edgecolor=color, hatch="///" if adaptive else None,
               linewidth=1.5 if adaptive else 0)
        ax.text(i, v + 40, f"{v:,.1f}".replace(",", " ").replace(".", ","),
                ha="center", va="bottom", fontsize=9, color=INK)

    ax.set_xticks(list(x), [b[0] for b in BARS], fontsize=9, color=MUTED)
    ax.set_ylabel("throughput médio (kbit/s)", color=MUTED)
    ax.set_ylim(0, max(values) * 1.12)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0)
    ax.set_title("Arquivo large, sem perda simulada (hachurado: timeout adaptativo)",
                 color=INK, fontsize=10, loc="left")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    for (label, *_), v in zip(BARS, values):
        print(f"{label.replace(chr(10), ' '):28} {v:8.1f} kbit/s")
    print(out)


if __name__ == "__main__":
    main()
