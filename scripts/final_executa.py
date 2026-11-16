#!/usr/bin/env python3
"""Roda todos os experimentos do relatório final numa única campanha.

Todas as execuções usam o mesmo servidor, o mesmo dia e a mesma semente de
arquivo do servidor, então o MD5 de cada arquivo é o mesmo em todas elas. Os
cenários rodam em sequência, com as configurações intercaladas, para que uma
piora passageira da rede não caia só sobre uma delas.

Para cada cenário:

    results/final/csv/metrics_grupo07_<protocolo>_<AAAAMMDD_HHMMSS>.csv
    results/final/logs/<id>.txt          saída do cliente (MD5 e DONE)
    results/final/execucoes.csv          uma linha por cenário

O cenário marcado com captura grava o tráfego com o dumpcap em
results/final/captura/<id>.pcapng (filtro udp and host <servidor>).

Uso (na raiz do repositório):
    python3 scripts/final_executa.py --server 137.131.178.229 --group grupo07

Retomável: cenários já presentes em execucoes.csv são pulados.
"""

import argparse
import csv
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "final")

PAIRS = [(0.05, 0.25), (0.25, 0.25), (0.5, 0.25), (0.125, 0.1),
         (0.125, 0.5), (1.0, 1.0)]  # o par 0,125/0,25 é o sr_adapt


def sr16(loss, adaptive=False, floor=50, alpha=0.125, beta=0.25):
    args = dict(protocol="sr", window=16, file="large", loss=loss)
    if adaptive:
        args.update(adaptive=True, min_timeout=floor, alpha=alpha, beta=beta)
    return args


def scenarios():
    s = []
    # Entrega 3 e visão integrada, sem perda.
    s += [("sr_fixo_p00", sr16(0.0)),
          ("sr_adapt_p00", sr16(0.0, True))]
    s += [(f"sr_piso{f}_p00", sr16(0.0, True, floor=f)) for f in (0, 100, 200)]
    s += [("gbn_fixo_p00", dict(protocol="gbn", window=16, file="large", loss=0.0)),
          ("saw_large_p00", dict(protocol="saw", file="large", loss=0.0))]
    # 5% de perda; o adaptativo é a execução capturada no Wireshark.
    s += [("sr_adapt_p05", dict(sr16(0.05, True), capture=True)),
          ("sr_fixo_p05", sr16(0.05))]
    # 10% de perda: piso, varredura de alfa e beta, fixo.
    s += [("sr_adapt_p10", sr16(0.10, True))]
    s += [(f"sr_piso{f}_p10", sr16(0.10, True, floor=f)) for f in (0, 100, 200)]
    s += [(f"sr_a{a:g}_b{b:g}_p10", sr16(0.10, True, alpha=a, beta=b))
          for a, b in PAIRS]
    s += [("sr_fixo_p10", sr16(0.10))]
    # Entrega 2 (small), intercalada por perda; saw_w1_p00 é também o small
    # da Entrega 1.
    for loss in (0.0, 0.05, 0.10):
        for proto, w in (("saw", 1), ("gbn", 4), ("gbn", 8), ("gbn", 16),
                         ("sr", 4), ("sr", 8), ("sr", 16)):
            args = dict(protocol=proto, file="small", loss=loss)
            if proto != "saw":
                args["window"] = w
            s.append((f"e2_{proto}_w{w}_p{round(loss * 100):02d}", args))
    # Entrega 1: medium (small e large já estão acima).
    s.append(("saw_medium_p00", dict(protocol="saw", file="medium", loss=0.0)))
    return s


FIELDS = ["id", "protocolo", "janela", "arquivo", "perda", "timeout_ms",
          "adaptativo", "piso_ms", "alpha", "beta", "inicio", "duracao_s",
          "csv", "md5", "md5_esperado", "done_ok", "desnecessarias"]


def command(args, cfg):
    cmd = [sys.executable, "cliente.py", "--server", args.server,
           "--group", args.group, "--file", cfg["file"],
           "--protocol", cfg["protocol"], "--loss", str(cfg["loss"]),
           "--seed", str(args.seed), "--timeout", str(args.timeout)]
    if "window" in cfg:
        cmd += ["--window", str(cfg["window"])]
    if cfg.get("adaptive"):
        cmd += ["--adaptive", "--min-timeout", str(cfg["min_timeout"]),
                "--alpha", str(cfg["alpha"]), "--beta", str(cfg["beta"])]
    return cmd


def start_capture(args, name):
    os.makedirs(os.path.join(OUT, "captura"), exist_ok=True)
    path = os.path.join(OUT, "captura", name + ".pcapng")
    proc = subprocess.Popen(["dumpcap", "-q", "-i", args.iface, "-f",
                             f"udp and host {args.server}", "-w", path],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    time.sleep(2)  # dá tempo de o dumpcap abrir a interface
    return proc


def stop_capture(proc):
    time.sleep(1)
    proc.send_signal(signal.SIGINT)
    proc.wait(timeout=30)


def run(args, name, cfg):
    cmd = command(args, cfg)
    cap = start_capture(args, name) if cfg.get("capture") else None
    started = datetime.now()
    t0 = time.time()
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env)
    if cap:
        stop_capture(cap)
    out = proc.stdout
    os.makedirs(os.path.join(OUT, "logs"), exist_ok=True)
    with open(os.path.join(OUT, "logs", name + ".txt"), "w",
              encoding="utf-8") as f:
        f.write(" ".join(cmd[1:]) + "\n\n" + out
                + ("\n--- stderr ---\n" + proc.stderr if proc.stderr else ""))

    m = re.search(r"métricas salvas em (.+?) \(", out)
    src = os.path.join(ROOT, m.group(1).strip()) if m else None
    md5 = re.search(r"MD5 calculado=(\w+) esperado=(\w+)", out)
    done = re.search(r"DONE ok=(\d)", out)
    if proc.returncode != 0 or "arquivo íntegro" not in out or not md5:
        if src and os.path.exists(src):
            os.makedirs(os.path.join(OUT, "falhas"), exist_ok=True)
            shutil.move(src, os.path.join(OUT, "falhas", os.path.basename(src)))
        return None
    os.makedirs(os.path.join(OUT, "csv"), exist_ok=True)
    dest = os.path.join(OUT, "csv", os.path.basename(src))
    shutil.move(src, dest)
    unnecessary = re.search(r"desnecessárias detectadas \(DATA duplicado\): (\d+)", out)
    return {
        "id": name, "protocolo": cfg["protocol"],
        "janela": cfg.get("window", 1), "arquivo": cfg["file"],
        "perda": cfg["loss"], "timeout_ms": args.timeout,
        "adaptativo": int(bool(cfg.get("adaptive"))),
        "piso_ms": cfg.get("min_timeout", ""), "alpha": cfg.get("alpha", ""),
        "beta": cfg.get("beta", ""), "inicio": started.isoformat(timespec="seconds"),
        "duracao_s": round(time.time() - t0, 1),
        "csv": os.path.relpath(dest, ROOT).replace("\\", "/"),
        "md5": md5.group(1), "md5_esperado": md5.group(2),
        "done_ok": done.group(1) if done else "",
        "desnecessarias": unnecessary.group(1) if unnecessary else "",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--server", required=True)
    parser.add_argument("--group", required=True)
    parser.add_argument("--timeout", type=float, default=1000.0,
                        help="timeout fixo (e inicial do adaptativo), em ms")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--iface", default="any",
                        help="interface de captura do dumpcap")
    parser.add_argument("--only", nargs="+", help="roda só estes ids")
    args = parser.parse_args()

    manifest = os.path.join(OUT, "execucoes.csv")
    done_ids = set()
    if os.path.exists(manifest):
        with open(manifest, newline="", encoding="utf-8") as f:
            done_ids = {r["id"] for r in csv.DictReader(f)}
    todo = [(n, c) for n, c in scenarios()
            if n not in done_ids and (not args.only or n in args.only)]
    print(f"{len(todo)} cenários a rodar", flush=True)

    failures = []
    for i, (name, cfg) in enumerate(todo, 1):
        print(f"[{datetime.now():%H:%M:%S}] {i}/{len(todo)} {name}", flush=True)
        row = None
        for attempt in range(2):
            row = run(args, name, cfg)
            if row:
                break
            print("    falhou, tentando de novo", flush=True)
        if not row:
            failures.append(name)
            print("    FALHOU duas vezes, veja o log", flush=True)
            continue
        new = not os.path.exists(manifest)
        with open(manifest, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            if new:
                w.writeheader()
            w.writerow(row)
        print(f"    OK em {row['duracao_s']} s, md5 {row['md5']}", flush=True)

    if failures:
        print("Falharam:", ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
