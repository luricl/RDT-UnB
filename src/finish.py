"""Encerramento da sessão do RDT-UnB v1.0: verificação MD5 e FIN -> DONE."""

import hashlib
import socket
import time
from dataclasses import dataclass

from src.packets import Done, Error, PacketError, build_fin, parse

DEFAULT_MAX_RETRIES = 5
RECV_BUFFER = 65535

# O servidor encerra a sessão no primeiro FIN; FINs seguintes recebem este erro.
SESSION_CLOSED = "sessao_nao_iniciada"


class FinishError(Exception):
    """O encerramento da sessão não pôde ser concluído."""


@dataclass(frozen=True)
class Finish:
    md5: str               # MD5 calculado sobre o arquivo remontado
    expected: str          # checksum recebido no OK
    server_ok: bool | None  # resposta do DONE; None se o DONE se perdeu

    @property
    def local_ok(self):
        return self.md5 == self.expected


def md5_hex(content):
    return hashlib.md5(content).hexdigest()


def wait_for_done(sock, server_addr, timeout_s):
    """Espera até `timeout_s` segundos pelo `DONE`.

    Devolve o `Done`, o `Error` de sessão encerrada, ou None se o prazo estourar.
    Outros pacotes (ex.: o ERROR do último ACK) são descartados.
    """
    deadline = time.monotonic() + timeout_s

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

        if isinstance(packet, Done):
            return packet
        if isinstance(packet, Error) and packet.msg == SESSION_CLOSED:
            return packet


def finish(sock, server_addr, content, expected, timeout_ms,
           max_retries=DEFAULT_MAX_RETRIES):
    """Calcula o MD5 do arquivo, envia o FIN e espera o DONE."""
    # O FIN leva o MD5 calculado, nunca o checksum do OK: o servidor só
    # compara as duas strings e não sabe se o arquivo foi baixado.
    md5 = md5_hex(content)
    fin = build_fin(md5)

    for attempt in range(max_retries + 1):
        sock.sendto(fin, server_addr)
        reply = wait_for_done(sock, server_addr, timeout_ms / 1000)
        if reply is None:
            continue
        if isinstance(reply, Done):
            return Finish(md5=md5, expected=expected, server_ok=reply.ok)
        if attempt > 0:
            # Um FIN anterior encerrou a sessão e o DONE se perdeu; vale a
            # verificação local.
            return Finish(md5=md5, expected=expected, server_ok=None)
        raise FinishError("servidor respondeu que não há sessão ativa")

    raise FinishError(f"sem DONE após {max_retries} retransmissões do FIN")
