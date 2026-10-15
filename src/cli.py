"""Interface de linha de comando do cliente RDT-UnB."""

import argparse
import os
import re
import socket
import sys
from dataclasses import dataclass

from src.finish import FinishError, finish
from src.handshake import HandshakeError, handshake
from src.saw import DownloadError, download

DEFAULT_PORT = 8080
DEFAULT_SEGMENT_SIZE = 512
DEFAULT_TIMEOUT_MS = 1000.0
DEFAULT_GBN_SR_WINDOW = 4
MAX_UDP_PAYLOAD = 65507

FILES = ("small", "medium", "large")
PROTOCOLS = ("saw", "gbn", "sr")

# O id do grupo vai dentro de `HELLO|grupo=<id>|...`, então não pode ter `|`.
GROUP_PATTERN = re.compile(r"[A-Za-z0-9_-]+")


@dataclass(frozen=True)
class Config:
    server: str
    port: int
    group: str
    file: str
    protocol: str
    window: int
    segment_size: int
    loss: float
    timeout_ms: float


def build_parser():
    parser = argparse.ArgumentParser(
        prog="cliente.py",
        description="Cliente RDT-UnB: transferência confiável sobre UDP.",
    )
    parser.add_argument("--server", required=True,
                        help="endereço IP ou hostname do servidor RDT-UnB")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help="porta UDP do servidor (padrão: %(default)s)")
    parser.add_argument("--group",
                        help="identificador do grupo, ex.: grupo07 (OBRIGATÓRIO)")
    parser.add_argument("--file", choices=FILES, default="small",
                        help="arquivo a baixar (padrão: %(default)s)")
    parser.add_argument("--protocol", choices=PROTOCOLS, default="saw",
                        help="protocolo de janela deslizante (padrão: %(default)s)")
    parser.add_argument("--window", type=int, default=None,
                        help="tamanho da janela para gbn/sr "
                             f"(padrão: {DEFAULT_GBN_SR_WINDOW}; saw usa sempre 1)")
    parser.add_argument("--segment-size", type=int, default=DEFAULT_SEGMENT_SIZE,
                        help="segment_size solicitado em bytes; o servidor pode "
                             "negociar outro valor (padrão: %(default)s)")
    parser.add_argument("--loss", type=float, default=0.0,
                        help="probabilidade de perda simulada, de 0 a 1 "
                             "(padrão: %(default)s, desligada)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_MS,
                        help="timeout de retransmissão em milissegundos "
                             "(padrão: %(default)s)")
    return parser


def parse_args(argv=None):
    """Lê e valida os argumentos. Em caso de erro, encerra com status 2."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.group is None or not args.group.strip():
        parser.error("--group é obrigatório (ex.: --group grupo07)")
    if not GROUP_PATTERN.fullmatch(args.group):
        parser.error("--group deve conter apenas letras, números, '-' e '_'")

    if not 1 <= args.port <= 65535:
        parser.error("--port deve estar entre 1 e 65535")

    if args.protocol == "saw":
        if args.window not in (None, 1):
            parser.error("--window só se aplica a gbn e sr; saw usa janela 1")
        window = 1
    else:
        window = DEFAULT_GBN_SR_WINDOW if args.window is None else args.window
        if window < 1:
            parser.error("--window deve ser pelo menos 1")

    if not 1 <= args.segment_size <= MAX_UDP_PAYLOAD:
        parser.error(f"--segment-size deve estar entre 1 e {MAX_UDP_PAYLOAD}")
    if not 0.0 <= args.loss <= 1.0:
        parser.error("--loss deve estar entre 0 e 1")
    if not args.timeout > 0:
        parser.error("--timeout deve ser maior que 0 (em milissegundos)")

    return Config(
        server=args.server,
        port=args.port,
        group=args.group,
        file=args.file,
        protocol=args.protocol,
        window=window,
        segment_size=args.segment_size,
        loss=args.loss,
        timeout_ms=args.timeout,
    )


def main(argv=None):
    config = parse_args(argv)
    print(f"RDT-UnB cliente | servidor={config.server}:{config.port} "
          f"grupo={config.group} arquivo={config.file}")
    print(f"protocolo={config.protocol} janela={config.window} "
          f"segment_size={config.segment_size} loss={config.loss} "
          f"timeout={config.timeout_ms}ms")
    if config.protocol != "saw":
        print("apenas --protocol saw está implementado por enquanto",
              file=sys.stderr)
        return 1

    # O recvfrom devolve o IP do remetente; resolver o hostname aqui permite
    # comparar o endereço das respostas com o do servidor.
    try:
        server_addr = (socket.gethostbyname(config.server), config.port)
    except socket.gaierror as exc:
        print(f"erro: não foi possível resolver {config.server}: {exc}",
              file=sys.stderr)
        return 1

    # Mesmo socket no handshake e na transferência: o servidor associa a
    # sessão ao endereço de origem do HELLO.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        ok = handshake(sock, server_addr, config.group, config.file,
                       config.segment_size, config.timeout_ms)
        print(f"handshake OK | file_size={ok.file_size} "
              f"total_segments={ok.total_segments} "
              f"segment_size={ok.segment_size} checksum={ok.checksum} "
              f"seed={ok.seed}")
        result = download(sock, server_addr, ok.total_segments,
                          config.timeout_ms)
        end = finish(sock, server_addr, result.content, ok.checksum,
                     config.timeout_ms)
    except (HandshakeError, DownloadError, FinishError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    finally:
        sock.close()

    os.makedirs("data", exist_ok=True)
    path = os.path.join("data", f"{config.file}.bin")
    with open(path, "wb") as f:
        f.write(result.content)
    print(f"arquivo salvo em {path} ({len(result.content)} bytes, "
          f"{result.retransmissions} retransmissões)")

    print(f"MD5 calculado={end.md5} esperado={end.expected}")
    if end.server_ok is None:
        print("DONE não recebido; vale a verificação local")
    else:
        print(f"DONE ok={int(end.server_ok)}")
    if not end.local_ok:
        print("erro: MD5 do arquivo não confere", file=sys.stderr)
        return 1
    print("arquivo íntegro")
    return 0
