"""Gravação das métricas por segmento em CSV (item T07).

Uma linha por segmento recebido. O arquivo é gerado ao fim de cada sessão em
`results/metrics_<grupo>_<protocolo>_<YYYYMMDD_HHMMSS>.csv`.
"""

import csv
import os
from datetime import datetime

COLUMNS = (
    "segment",           # número de sequência do segmento
    "timestamp",         # chegada do DATA, ISO 8601 com fuso (relógio do sistema)
    "size_bytes",        # tamanho do payload recebido
    "rtt_ms",            # amostra de RTT: último REQ enviado -> DATA recebido
    "rtt_estimated_ms",  # EstimatedRTT (EWMA) após este segmento
    "timeout_ms",        # timeout em vigor ao pedir este segmento
    "throughput_kbps",   # size_bytes * 8 / tempo total do segmento (kbit/s)
    "retransmissions",   # REQs reenviados para este segmento
    "timeout_occurred",  # 1 se houve pelo menos um timeout, senão 0
    "window_size",       # 1 no Stop-and-Wait
    "protocol",          # saw, gbn ou sr
    "loss_simulated",    # 1 se pelo menos uma perda deste segmento foi simulada
)

DEFAULT_DIR = "results"


def iso_timestamp(epoch_s):
    """Converte `time.time()` para ISO 8601 no fuso local, com microssegundos.

    É o mesmo relógio que o Wireshark usa para marcar os pacotes, então dá
    para casar cada linha do CSV com o datagrama capturado.
    """
    return datetime.fromtimestamp(epoch_s).astimezone().isoformat(
        timespec="microseconds")


def metrics_filename(group, protocol, started_at):
    """Nome do CSV: metrics_<grupo>_<protocolo>_<YYYYMMDD_HHMMSS>.csv."""
    stamp = started_at.strftime("%Y%m%d_%H%M%S")
    return f"metrics_{group}_{protocol}_{stamp}.csv"


def _fmt(value):
    """Formata números com 3 casas; vazio para valor ausente (None)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, float):
        return f"{value:.3f}"
    return value


def segment_row(stat, window_size, protocol):
    """Monta a linha do CSV (dict coluna -> valor) para um SegmentStats."""
    return {
        "segment": stat.seq,
        "timestamp": iso_timestamp(stat.received_at),
        "size_bytes": stat.size_bytes,
        "rtt_ms": _fmt(stat.rtt_ms),
        "rtt_estimated_ms": _fmt(stat.rtt_estimated_ms),
        "timeout_ms": _fmt(stat.timeout_ms),
        "throughput_kbps": _fmt(stat.throughput_kbps),
        "retransmissions": stat.retransmissions,
        "timeout_occurred": _fmt(stat.timeout_occurred),
        "window_size": window_size,
        "protocol": protocol,
        "loss_simulated": _fmt(stat.loss_simulated),
    }


def write_metrics(segments, group, protocol, window_size, started_at,
                  directory=DEFAULT_DIR):
    """Grava o CSV da sessão e devolve o caminho do arquivo criado.

    Grava mesmo com `segments` vazio (só o cabeçalho), para que toda sessão
    deixe registro, inclusive as que falharam.
    """
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory,
                        metrics_filename(group, protocol, started_at))
    # newline="" evita linhas em branco extras no Windows (exigência do csv).
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for stat in segments:
            writer.writerow(segment_row(stat, window_size, protocol))
    return path


def summarize_metrics(path):
    """Lê um CSV de métricas e devolve as métricas agregadas da sessão.

    Tudo vem do CSV, para que o resumo do terminal bata com o arquivo usado
    nos gráficos e no relatório. Devolve None se o CSV não tiver segmentos.
    """
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None

    # O CSV fica em ordem de segmento; a ordem de chegada é a do timestamp.
    by_arrival = sorted(rows, key=lambda r: datetime.fromisoformat(r["timestamp"]))

    # Tempo total do 1º REQ ao último DATA, como em scripts/entrega02_analisa.py.
    # O CSV não guarda o instante do REQ; ele é recuperado de cada segmento
    # pela vazão: elapsed (ms) = size_bytes * 8 / throughput_kbps.
    def first_req_s(r):
        arrival = datetime.fromisoformat(r["timestamp"]).timestamp()
        thr = float(r["throughput_kbps"]) if r["throughput_kbps"] else 0.0
        elapsed_ms = (int(r["size_bytes"]) * 8 / thr if thr > 0
                      else float(r["rtt_ms"]))
        return arrival - elapsed_ms / 1000

    start = min(first_req_s(r) for r in rows)
    end = datetime.fromisoformat(by_arrival[-1]["timestamp"]).timestamp()
    duration_s = end - start

    total_bytes = sum(int(r["size_bytes"]) for r in rows)
    rtts = [float(r["rtt_ms"]) for r in rows]
    per_segment = [float(r["throughput_kbps"]) for r in rows
                   if r["throughput_kbps"]]
    estimates = [r["rtt_estimated_ms"] for r in by_arrival
                 if r["rtt_estimated_ms"]]

    return {
        "segments": len(rows),
        "total_bytes": total_bytes,
        "duration_s": duration_s,
        # Vazão do protocolo: o arquivo inteiro sobre o tempo total. É a que
        # mostra o ganho da janela no GBN e no SR.
        "throughput_kbps": (total_bytes * 8 / duration_s / 1000
                            if duration_s > 0 else None),
        # Média da coluna throughput_kbps: vazão de cada segmento isolado.
        "segment_throughput_kbps": (sum(per_segment) / len(per_segment)
                                    if per_segment else None),
        "retransmissions": sum(int(r["retransmissions"]) for r in rows),
        "timeouts": sum(int(r["timeout_occurred"]) for r in rows),
        "loss_simulated": sum(int(r["loss_simulated"]) for r in rows),
        "rtt_mean_ms": sum(rtts) / len(rtts),
        "rtt_min_ms": min(rtts),
        "rtt_max_ms": max(rtts),
        "rtt_estimated_ms": float(estimates[-1]) if estimates else None,
    }


def format_summary(summary):
    """Linhas do resumo para o terminal."""
    def num(value, unit, digits=1):
        return "-" if value is None else f"{value:.{digits}f} {unit}"

    return [
        f"segmentos recebidos:      {summary['segments']} "
        f"({summary['total_bytes']} bytes)",
        f"tempo total:              {num(summary['duration_s'], 's', 2)} "
        "(do 1º REQ ao último DATA)",
        f"vazão efetiva:            {num(summary['throughput_kbps'], 'kbps')} "
        "(bytes * 8 / tempo total)",
        f"vazão média por segmento: "
        f"{num(summary['segment_throughput_kbps'], 'kbps')} "
        "(média da coluna throughput_kbps)",
        f"retransmissões:           {summary['retransmissions']} "
        f"({summary['timeouts']} segmentos com timeout)",
        f"perda simulada:           {summary['loss_simulated']} segmentos",
        f"RTT:                      médio {num(summary['rtt_mean_ms'], 'ms')}, "
        f"mín {num(summary['rtt_min_ms'], 'ms')}, "
        f"máx {num(summary['rtt_max_ms'], 'ms')}",
        f"RTT estimado final:       {num(summary['rtt_estimated_ms'], 'ms')}",
    ]
