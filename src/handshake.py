"""Handshake HELLO/OK do RDT-UnB v1.0.

O cliente envia `HELLO` e o servidor responde `OK` com os metadados do arquivo.
Como é UDP, o HELLO (ou o OK) pode se perder: reenviamos o HELLO a cada timeout.
"""

import socket
import time

from src.packets import Ok, PacketError, build_hello, parse

DEFAULT_MAX_ATTEMPTS = 5
RECV_BUFFER = 65535


class HandshakeError(Exception):
    """O handshake não completou (sem resposta ou resposta inaceitável)."""


def wait_for_ok(sock, server_addr, timeout_s):
    """Espera até `timeout_s` segundos por um `OK` do servidor.

    Devolve o `Ok` recebido, ou None se o prazo estourar sem um OK válido.
    """
    deadline = time.monotonic() + timeout_s
    time_left = deadline

    while time_left > 0:
        sock.settimeout(time_left)
        try:
            data, addr = sock.recvfrom(RECV_BUFFER)
        except socket.timeout:
            return None

        if addr != server_addr:
            continue
        
        try:
            packet = parse(data)
        except PacketError:
            continue
        
        if isinstance(packet, Ok):
            return packet
        
        time_left = deadline - time.monotonic()

    return None

def handshake(sock, server_addr, group, file, segment_size,
              timeout_ms, max_attempts=DEFAULT_MAX_ATTEMPTS):
    """Executa o handshake e devolve o `Ok` do servidor.

    O `segment_size` do `Ok` é o que vale para o resto da transferência: o
    servidor pode negociar um valor diferente do solicitado.
    """
    hello = build_hello(group, segment_size, file)
    for _ in range(max_attempts):
        sock.sendto(hello, server_addr)
        ok = wait_for_ok(sock, server_addr, timeout_ms / 1000)
        if ok is not None:
            if ok.segment_size < 1 or ok.total_segments < 0:
                raise HandshakeError(f"OK com valores inválidos: {ok}")
            return ok
    raise HandshakeError(
        f"sem resposta do servidor após {max_attempts} tentativas de HELLO")
