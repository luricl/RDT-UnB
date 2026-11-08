"""Selective Repeat do RDT-UnB v1.0: até N REQs em voo, um timer por segmento.

Diferenças em relação ao Stop-and-Wait:
- até `window` segmentos podem estar pedidos e sem DATA ao mesmo tempo;
- cada segmento pendente tem seu próprio prazo (timer);
- no timeout, só o REQ daquele segmento é reenviado;
- DATA que chega fora de ordem é guardado no buffer, e o arquivo é montado
  na ordem certa no final.
"""

import random
import socket
import time
from dataclasses import dataclass

from src.packets import Data, PacketError, build_ack, build_req, parse
from src.rtt import DEFAULT_ALPHA, DEFAULT_BETA, RttEstimator
from src.saw import Download, DownloadError, SegmentStats

DEFAULT_MAX_RETRIES = 10
RECV_BUFFER = 65535


@dataclass
class Pending:
    """Segmento com REQ enviado e DATA ainda não recebido."""
    first_sent_at: float          # primeiro REQ (para elapsed_ms)
    sent_at: float                # último REQ (para rtt_ms, como no SAW)
    deadline: float               # instante em que o timer deste segmento vence
    timeout_ms: float             # timeout aplicado ao último REQ (vai ao CSV)
    retransmissions: int = 0
    loss_simulated: bool = False  # algum DATA deste segmento foi descartado


def receive_data(sock, server_addr, deadline):
    """Espera um `DATA` do servidor até o instante `deadline` (time.monotonic).

    Devolve o `Data` recebido, ou None se o prazo vencer. Pacotes de outra
    origem, malformados ou de outro tipo (ex.: o ERROR do ACK) são ignorados.
    """
    while True:
        time_left = deadline - time.monotonic()
        if time_left <= 0:
            return None
        sock.settimeout(time_left)
        try:
            raw, addr = sock.recvfrom(RECV_BUFFER)
        except socket.timeout:
            return None

        if addr != server_addr:
            continue
        try:
            packet = parse(raw)
        except PacketError:
            continue
        if isinstance(packet, Data):
            return packet


def download(sock, server_addr, total_segments, timeout_ms, window,
             max_retries=DEFAULT_MAX_RETRIES, loss=0.0, seed=0,
             adaptive=False, alpha=DEFAULT_ALPHA, beta=DEFAULT_BETA):
    """Baixa todos os segmentos em Selective Repeat e remonta o arquivo.

    `loss` e `seed` funcionam como no SAW: cada DATA de um segmento pendente
    é descartado com probabilidade `loss`, com sorteio reproduzível por `seed`.

    Com `adaptive`, `timeout_ms` vale só até a primeira amostra de RTT; depois
    cada REQ usa EstimatedRTT + 4 * DevRTT (`alpha` e `beta` ajustam as EWMAs).
    """
    rng = random.Random(seed)
    estimator = RttEstimator(alpha=alpha, beta=beta)

    def current_timeout_ms():
        return estimator.timeout_ms(timeout_ms) if adaptive else timeout_ms

    base = 0        # segmento mais antigo ainda sem DATA
    next_seq = 0    # próximo segmento a ser pedido
    pending = {}    # seq -> Pending: pedidos em voo
    buffer = {}     # seq -> payload: recebidos, inclusive fora de ordem
    stats = []

    while base < total_segments:
        # 1. Enche a janela: pede segmentos novos enquanto houver espaço.
        while next_seq < base + window and next_seq < total_segments:
            sock.sendto(build_req(next_seq), server_addr)
            now = time.monotonic()
            t_ms = current_timeout_ms()
            pending[next_seq] = Pending(first_sent_at=now, sent_at=now,
                                        deadline=now + t_ms / 1000,
                                        timeout_ms=t_ms)
            next_seq += 1

        # 2. Espera um DATA até o timer mais próximo vencer.
        nearest_deadline = min(p.deadline for p in pending.values())
        data = receive_data(sock, server_addr, nearest_deadline)

        # Só interessa DATA de segmento pendente; duplicatas de segmentos já
        # recebidos não estão em `pending` e são descartadas.
        if data is not None and data.seq in pending:
            p = pending[data.seq]
            if loss > 0.0 and rng.random() < loss:
                # Perda simulada: finge que o DATA não chegou e deixa o timer
                # deste segmento vencer normalmente.
                p.loss_simulated = True
            else:
                del pending[data.seq]
                buffer[data.seq] = data.payload
                stats.append(segment_stats(data, p, estimator))
                sock.sendto(build_ack(data.seq), server_addr)
                # Desliza a janela por cima de tudo que já está no buffer.
                while base in buffer:
                    base += 1

        # 3. Retransmite só os segmentos cujo timer venceu.
        now = time.monotonic()
        for seq, p in pending.items():
            if p.deadline > now:
                continue
            if p.retransmissions == max_retries:
                raise DownloadError(
                    f"segmento {seq}: sem resposta após {max_retries} "
                    "retransmissões", segments=sorted_by_seq(stats))
            sock.sendto(build_req(seq), server_addr)
            p.retransmissions += 1
            p.sent_at = now
            p.timeout_ms = current_timeout_ms()
            p.deadline = now + p.timeout_ms / 1000

    content = b"".join(buffer[seq] for seq in range(total_segments))
    return Download(content=content, segments=sorted_by_seq(stats))


def segment_stats(data, p, estimator):
    """Monta o SegmentStats de um segmento que acabou de chegar."""
    now = time.monotonic()
    # RTT a partir do último REQ, e só amostras sem retransmissão entram na
    # EWMA (algoritmo de Karn), como no SAW.
    rtt_ms = (now - p.sent_at) * 1000
    if p.retransmissions == 0:
        estimator.update(rtt_ms)
    return SegmentStats(seq=data.seq, received_at=time.time(),
                        size_bytes=len(data.payload), rtt_ms=rtt_ms,
                        retransmissions=p.retransmissions,
                        rtt_estimated_ms=estimator.estimated_ms,
                        timeout_ms=p.timeout_ms,
                        elapsed_ms=(now - p.first_sent_at) * 1000,
                        loss_simulated=p.loss_simulated)


def sorted_by_seq(stats):
    """O CSV fica em ordem de segmento; a ordem de chegada está no timestamp."""
    return sorted(stats, key=lambda s: s.seq)
