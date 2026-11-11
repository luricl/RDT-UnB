#!/usr/bin/env python3
"""Varre pares (alpha, beta) da EWMA do RTT no SR com timeout adaptativo.

Para cada par e cada perda, roda o cliente (`--protocol sr --adaptive`) com a
mesma janela e seed, e guarda:

    results/ewma/<perda>/a<alpha>_b<beta>.csv    métricas por segmento
    results/ewma/<perda>/logs/<mesmo nome>.log   saída do cliente
    results/ewma/resumo.csv                      uma linha por execução

Uso (na raiz do repositório):
    python scripts/ewma_executa.py --server 137.131.178.229 --group grupo07

Retomável: execuções que já têm CSV são puladas (use --force para refazer).
"""

import argparse
import csv
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.metrics import summarize_metrics  # noqa: E402

# O primeiro par é o padrão da RFC 6298 (baseline).
PAIRS = [(0.125, 0.25), (0.05, 0.25), (0.25, 0.25), (0.5, 0.25),
         (0.125, 0.1), (0.125, 0.5), (1.0, 1.0)]
LOSSES = [0.0, 0.10]

SUMMARY_FIELDS = ["perda", "alpha", "beta", "duracao_s", "vazao_kbps",
                  "timeouts", "retransmissoes", "timeout_medio_ms",
                  "timeout_min_ms", "rtt_estimado_final_ms",
                  "rtt_estimado_desvio_ms", "csv"]


def run_name(alpha, beta):
    return f"a{alpha:g}_b{beta:g}"


def loss_dir(loss):
    return f"p{round(loss * 100):02d}"


def run(args, alpha, beta, loss, out_dir):
    name = run_name(alpha, beta)
    cmd = [sys.executable, "cliente.py", "--server", args.server,
           "--port", str(args.port), "--group", args.group,
           "--file", args.file, "--protocol", "sr",
           "--window", str(args.window), "--adaptive",
           "--alpha", str(alpha), "--beta", str(beta),
           "--loss", str(loss), "--seed", str(args.seed),
           "--timeout", str(args.timeout)]
    print(f"[{datetime.now():%H:%M:%S}] {loss_dir(loss)} {name}", flush=True)

    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    started = time.time()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env)
    os.makedirs(os.path.join(out_dir, "logs"), exist_ok=True)
    with open(os.path.join(out_dir, "logs", name + ".log"), "w",
              encoding="utf-8") as f:
        f.write(" ".join(cmd) + "\n\n" + proc.stdout
                + "\n--- stderr ---\n" + proc.stderr)

    m = re.search(r"métricas salvas em (.+?) \(", proc.stdout)
    src = os.path.join(ROOT, m.group(1).strip()) if m else None
    if proc.returncode != 0 or "arquivo íntegro" not in proc.stdout \
            or not src or not os.path.exists(src):
        print(f"    FALHOU (código {proc.returncode}), veja o log", flush=True)
        return None
    dest = os.path.join(out_dir, name + ".csv")
    shutil.move(src, dest)
    print(f"    OK em {time.time() - started:.1f} s", flush=True)
    return dest


def summarize(loss, alpha, beta, csv_path):
    s = summarize_metrics(csv_path)
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    timeouts = [float(r["timeout_ms"]) for r in rows if r["timeout_ms"]]
    est = [float(r["rtt_estimated_ms"]) for r in rows if r["rtt_estimated_ms"]]
    return {
        "perda": loss, "alpha": alpha, "beta": beta,
        "duracao_s": round(s["duration_s"], 3),
        "vazao_kbps": round(s["throughput_kbps"], 1),
        "timeouts": s["timeouts"], "retransmissoes": s["retransmissions"],
        "timeout_medio_ms": round(statistics.fmean(timeouts), 2),
        "timeout_min_ms": round(min(timeouts), 2),
        "rtt_estimado_final_ms": round(s["rtt_estimated_ms"], 2),
        "rtt_estimado_desvio_ms": round(statistics.pstdev(est), 2),
        "csv": os.path.relpath(csv_path, ROOT).replace("\\", "/"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--server", required=True)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--group", required=True)
    parser.add_argument("--file", default="medium",
                        choices=("small", "medium", "large"))
    parser.add_argument("--window", type=int, default=16)
    parser.add_argument("--timeout", type=float, default=80.0,
                        help="timeout inicial em ms, até a 1ª amostra de RTT")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default=os.path.join("results", "ewma"))
    parser.add_argument("--losses", type=float, nargs="+", default=LOSSES)
    parser.add_argument("--force", action="store_true",
                        help="refaz execuções que já têm CSV")
    args = parser.parse_args()

    base = os.path.join(ROOT, args.out)
    # Ordem intercalada: para cada perda, todos os pares em sequência.
    for loss in args.losses:
        out_dir = os.path.join(base, loss_dir(loss))
        os.makedirs(out_dir, exist_ok=True)
        for alpha, beta in PAIRS:
            dest = os.path.join(out_dir, run_name(alpha, beta) + ".csv")
            if os.path.exists(dest) and not args.force:
                print(f"{loss_dir(loss)} {run_name(alpha, beta)}: já existe, pulando")
                continue
            run(args, alpha, beta, loss, out_dir)

    # O resumo é refeito com tudo que existe em disco, inclusive de execuções
    # anteriores, para continuar válido ao retomar.
    summary = []
    for loss in args.losses:
        for alpha, beta in PAIRS:
            path = os.path.join(base, loss_dir(loss),
                                run_name(alpha, beta) + ".csv")
            if os.path.exists(path):
                summary.append(summarize(loss, alpha, beta, path))
    if not summary:
        print("Nenhuma execução concluída.")
        return 1
    with open(os.path.join(base, "resumo.csv"), "w", newline="",
              encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(summary)

    print(f"\n{'perda':>5} {'alpha':>6} {'beta':>5} {'tempo(s)':>9} "
          f"{'kbps':>8} {'timeouts':>8} {'TO médio':>9} {'estim.dp':>8}")
    for r in summary:
        print(f"{r['perda']:>5} {r['alpha']:>6g} {r['beta']:>5g} "
              f"{r['duracao_s']:>9} {r['vazao_kbps']:>8} {r['timeouts']:>8} "
              f"{r['timeout_medio_ms']:>9} {r['rtt_estimado_desvio_ms']:>8}")
    print(f"\nResumo salvo em {os.path.relpath(os.path.join(base, 'resumo.csv'), ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
