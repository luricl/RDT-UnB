#!/usr/bin/env python3
"""Roda todos os cenários da Entrega 2 contra o servidor e guarda os resultados.

Cenários: SAW (janela 1), GBN e SR com janelas 4, 8 e 16, cada um sem perda,
com 5% e com 10% de perda simulada (21 execuções). Para cada execução:

    results/entrega02/<protocolo>_w<janela>_p<perda>.csv   métricas por segmento
    results/entrega02/logs/<mesmo nome>.log                saída do cliente
    results/entrega02/execucoes.json                       resumo (MD5, DONE, tempo)

Uso (na raiz do repositório):
    python scripts/entrega02_executa.py --server 137.131.178.229 --group grupo07

É retomável: cenários que já terminaram com MD5 OK são pulados (use --force
para refazer). As execuções rodam em ordem intercalada (para cada perda, todos
os protocolos) para que uma piora momentânea da rede não afete só um protocolo.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIGS = [("saw", 1), ("gbn", 4), ("gbn", 8), ("gbn", 16),
           ("sr", 4), ("sr", 8), ("sr", 16)]
LOSSES = [0.0, 0.05, 0.10]


def scenario_name(protocol, window, loss):
    return f"{protocol}_w{window}_p{round(loss * 100):02d}"


def parse_output(text):
    """Extrai do stdout do cliente o CSV gerado, o MD5 e a resposta do DONE."""
    info = {}
    m = re.search(r"métricas salvas em (.+?) \((\d+) segmentos\)", text)
    if m:
        info["csv_original"] = m.group(1).strip()
        info["segments"] = int(m.group(2))
    m = re.search(r"MD5 calculado=([0-9a-f]+) esperado=([0-9a-f]+)", text)
    if m:
        info["md5"], info["md5_expected"] = m.group(1), m.group(2)
    m = re.search(r"DONE ok=(\d)", text)
    info["done_ok"] = int(m.group(1)) if m else None
    m = re.search(r"checksum=([0-9a-f]+) seed=(\S+)", text)
    if m:
        info["seed_arquivo"] = m.group(2)
    info["integro"] = "arquivo íntegro" in text
    return info


def run(args, protocol, window, loss, out_dir):
    name = scenario_name(protocol, window, loss)
    cmd = [sys.executable, "cliente.py", "--server", args.server,
           "--port", str(args.port), "--group", args.group,
           "--file", args.file, "--protocol", protocol,
           "--loss", str(loss), "--seed", str(args.seed),
           "--timeout", str(args.timeout)]
    if protocol != "saw":
        cmd += ["--window", str(window)]

    print(f"[{datetime.now():%H:%M:%S}] {name}: {' '.join(cmd[1:])}", flush=True)
    started = time.time()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    wall = time.time() - started
    output = proc.stdout + "\n--- stderr ---\n" + proc.stderr

    os.makedirs(os.path.join(out_dir, "logs"), exist_ok=True)
    with open(os.path.join(out_dir, "logs", name + ".log"), "w",
              encoding="utf-8") as f:
        f.write(" ".join(cmd) + "\n\n" + output)

    info = parse_output(proc.stdout)
    csv_dest = None
    if "csv_original" in info:
        src = os.path.join(ROOT, info["csv_original"])
        if os.path.exists(src):
            csv_dest = os.path.join(out_dir, name + ".csv")
            shutil.move(src, csv_dest)

    record = {
        "cenario": name, "protocolo": protocol, "janela": window,
        "perda": loss, "arquivo": args.file, "seed": args.seed,
        "timeout_ms": args.timeout, "returncode": proc.returncode,
        "inicio": datetime.fromtimestamp(started).isoformat(timespec="seconds"),
        "duracao_processo_s": round(wall, 3),
        "csv": os.path.relpath(csv_dest, ROOT).replace("\\", "/") if csv_dest else None,
        **{k: v for k, v in info.items() if k != "csv_original"},
    }
    ok = proc.returncode == 0 and info.get("integro")
    status = "OK" if ok else f"FALHOU (código {proc.returncode})"
    print(f"    {status} em {wall:.1f} s, DONE ok={info.get('done_ok')}",
          flush=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--server", required=True)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--group", required=True)
    parser.add_argument("--file", default="small",
                        choices=("small", "medium", "large"))
    parser.add_argument("--timeout", type=float, default=1000.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default=os.path.join("results", "entrega02"))
    parser.add_argument("--only", help="roda só cenários cujo nome contém "
                        "este texto (ex.: gbn_w16)")
    parser.add_argument("--force", action="store_true",
                        help="refaz cenários que já terminaram com sucesso")
    args = parser.parse_args()

    out_dir = os.path.join(ROOT, args.out)
    os.makedirs(out_dir, exist_ok=True)
    index_path = os.path.join(out_dir, "execucoes.json")
    index = {}
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            index = {r["cenario"]: r for r in json.load(f)}

    plan = [(p, w, l) for l in LOSSES for p, w in CONFIGS]
    if args.only:
        plan = [s for s in plan if args.only in scenario_name(*s)]

    for protocol, window, loss in plan:
        name = scenario_name(protocol, window, loss)
        done = index.get(name)
        if done and done["returncode"] == 0 and done.get("integro") and not args.force:
            print(f"{name}: já executado com sucesso, pulando")
            continue
        index[name] = run(args, protocol, window, loss, out_dir)
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(sorted(index.values(), key=lambda r: r["cenario"]), f,
                      indent=2, ensure_ascii=False)

    falhas = [r["cenario"] for r in index.values()
              if r["returncode"] != 0 or not r.get("integro")]
    print(f"\n{len(index) - len(falhas)}/{len(index)} cenários OK.")
    if falhas:
        print("Com falha (rode de novo para refazer só estes):", ", ".join(falhas))
        return 1
    print("Próximo passo: python scripts/entrega02_analisa.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
