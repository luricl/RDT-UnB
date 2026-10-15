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
