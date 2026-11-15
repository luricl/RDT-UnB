#!/usr/bin/env python3
"""Cruza uma captura do Wireshark com o CSV da mesma execução.

Uso: python3 scripts/wireshark_analisa.py <captura.pcapng> <metrics.csv>

Imprime:
- os frames do HELLO, OK, primeiro REQ, FIN e DONE (visão geral);
- os REQs repetidos (retransmissões), com o frame do REQ original, o do
  retransmitido, o delta entre eles e a linha do CSV;
- o RTT de cada segmento sem retransmissão medido na captura (REQ ->
  primeiro DATA) contra o rtt_ms do CSV;
- o deslocamento entre o timestamp do CSV e a chegada do DATA na captura.

Precisa do tshark no PATH.
"""
import csv
import statistics
import subprocess
import sys
from datetime import datetime


def packets(pcap):
    out = subprocess.run(
        ["tshark", "-r", pcap, "-T", "fields", "-e", "frame.number",
         "-e", "frame.time_relative", "-e", "frame.time_epoch",
         "-e", "udp.payload"],
        capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        num, rel, epoch, payload = line.split("\t")
        head = bytes.fromhex(payload[:160]).split(b"|")
        kind = head[0].decode("ascii", "replace")
        fields = dict(f.decode("ascii", "replace").split("=", 1)
                      for f in head[1:3] if b"=" in f)
        yield int(num), float(rel), float(epoch), kind, fields


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    pcap, csv_path = sys.argv[1:]
    pk = list(packets(pcap))
    reqs, datas = {}, {}
    marks = {}
    for num, rel, epoch, kind, f in pk:
        if kind in ("HELLO", "OK", "FIN", "DONE") and kind not in marks:
            marks[kind] = (num, rel)
        if kind == "REQ":
            reqs.setdefault(int(f["seq"]), []).append((num, rel, epoch))
            marks.setdefault("REQ0", (num, rel))
        if kind == "DATA":
            datas.setdefault(int(f["seq"]), []).append((num, rel, epoch))

    print("Visão geral (frame, t em s):")
    for k in ("HELLO", "OK", "REQ0", "FIN", "DONE"):
        if k in marks:
            print(f"  {k:6} frame {marks[k][0]:>6}  t={marks[k][1]:.6f}")
    print(f"  {len(pk)} pacotes, {sum(map(len, reqs.values()))} REQ, "
          f"{sum(map(len, datas.values()))} DATA")

    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = {int(r["segment"]): r for r in csv.DictReader(f)}

    retx = sorted(s for s, v in reqs.items() if len(v) > 1)
    print(f"\nSegmentos com REQ repetido: {len(retx)} "
          f"(CSV: {sum(1 for r in rows.values() if r['retransmissions'] != '0')})")
    print("  seq  REQ orig (frame,t)       REQ retx (frame,t)       delta_ms  "
          "DATAs (frames)        CSV: retx loss timeout_ms timestamp")
    for s in retx[:15]:
        (n1, t1, _), (n2, t2, _) = reqs[s][:2]
        d = [n for n, _, _ in datas.get(s, [])]
        r = rows[s]
        print(f"  {s:>5} {n1:>6} {t1:10.6f}   {n2:>6} {t2:10.6f}   "
              f"{(t2 - t1) * 1000:8.2f}  {str(d):20} {r['retransmissions']:>3} "
              f"{r['loss_simulated']:>4} {r['timeout_ms']:>9} {r['timestamp']}")

    diffs, ws, cl, offs = [], [], [], []
    for s, r in rows.items():
        if s not in datas:
            continue
        if r["rtt_ms"] and len(reqs.get(s, [])) == 1:
            w = (datas[s][0][1] - reqs[s][0][1]) * 1000
            ws.append(w)
            cl.append(float(r["rtt_ms"]))
            diffs.append(float(r["rtt_ms"]) - w)
        csv_t = datetime.fromisoformat(r["timestamp"]).timestamp()
        # O DATA aceito é o último que chegou antes do timestamp do CSV.
        before = [e for _, _, e in datas[s] if e <= csv_t + 0.005]
        if before:
            offs.append((csv_t - before[-1]) * 1000)
    print(f"\nRTT sem retransmissão ({len(ws)} segmentos):")
    print(f"  mediana Wireshark {statistics.median(ws):.3f} ms, "
          f"CSV {statistics.median(cl):.3f} ms, diferença média "
          f"{statistics.fmean(diffs):.3f} ms (mín {min(diffs):.3f}, "
          f"máx {max(diffs):.3f})")
    for s in (0, 1, 5000, 10000, max(rows)):
        if s in datas and rows[s]["rtt_ms"] and len(reqs[s]) == 1:
            w = (datas[s][0][1] - reqs[s][0][1]) * 1000
            print(f"  seg {s:>5}: REQ frame {reqs[s][0][0]}, DATA frame "
                  f"{datas[s][0][0]}, Wireshark {w:.3f} ms, CSV "
                  f"{rows[s]['rtt_ms']} ms")
    print(f"\nTimestamp do CSV - chegada do DATA na captura: mediana "
          f"{statistics.median(offs):.3f} ms (mín {min(offs):.3f}, "
          f"máx {max(offs):.3f})")


if __name__ == "__main__":
    main()
