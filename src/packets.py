"""Construção e interpretação dos pacotes do protocolo RDT-UnB v1.0.

Todo pacote é texto separado por `|`, exceto o payload do DATA, que é binário.
Por isso tudo aqui trabalha com `bytes`, nunca com `str`, na fronteira com o socket.
"""

from dataclasses import dataclass

SEP = b"|"


class PacketError(ValueError):
    """Pacote recebido que não segue o formato do RDT-UnB v1.0."""


# ---------------------------------------------------------------------------
# Pacotes recebidos do servidor
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Ok:
    file_size: int
    checksum: str
    seed: str
    total_segments: int
    segment_size: int


@dataclass(frozen=True)
class Data:
    seq: int
    payload: bytes


@dataclass(frozen=True)
class Done:
    ok: bool


@dataclass(frozen=True)
class Pong:
    time: float


@dataclass(frozen=True)
class Error:
    # Não está na especificação: o servidor responde assim a pacotes que não
    # reconhece (ex.: `ERROR|msg=tipo_desconhecido_ACK` após cada ACK).
    msg: str


# ---------------------------------------------------------------------------
# Builders: pacotes que o cliente envia
# ---------------------------------------------------------------------------

def _field(value):
    """Converte um valor para texto e garante que ele não quebra o formato."""
    text = str(value)
    if "|" in text or "=" in text:
        raise ValueError(f"valor inválido para o protocolo: {text!r}")
    return text


def _seq(seq):
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
        raise ValueError(f"seq deve ser um inteiro >= 0: {seq!r}")
    return seq


def build_hello(group, segment_size, file):
    return (f"HELLO|grupo={_field(group)}|segment_size={_field(segment_size)}"
            f"|file={_field(file)}").encode("ascii")


def build_req(seq):
    return f"REQ|seq={_seq(seq)}".encode("ascii")


def build_ack(seq):
    return f"ACK|seq={_seq(seq)}".encode("ascii")


def build_fin(checksum):
    return f"FIN|checksum={_field(checksum)}".encode("ascii")


def build_ping():
    return b"PING"


# ---------------------------------------------------------------------------
# Parsers: pacotes que o cliente recebe
# ---------------------------------------------------------------------------

def _fields(parts):
    """Transforma [b"chave=valor", ...] em {"chave": "valor", ...}."""
    fields = {}
    for part in parts:
        try:
            key, sep, value = part.decode("ascii").partition("=")
        except UnicodeDecodeError:
            raise PacketError(f"campo com bytes não ASCII: {part[:20]!r}") from None
        if not sep or not key:
            raise PacketError(f"campo sem '=': {part!r}")
        fields[key] = value
    return fields


def _get(fields, key, convert=str):
    """Lê um campo obrigatório já convertido para o tipo certo."""
    if key not in fields:
        raise PacketError(f"campo obrigatório ausente: {key}")
    try:
        return convert(fields[key])
    except ValueError:
        raise PacketError(f"valor inválido em {key}: {fields[key]!r}") from None


def _parse_data(packet):
    # Só as 3 primeiras barras separam campos; o resto é o payload binário,
    # que pode conter o byte `|` e não pode ser dividido.
    parts = packet.split(SEP, 3)
    if len(parts) != 4:
        raise PacketError("DATA incompleto")
    _, seq_part, total_part, payload = parts
    fields = _fields([seq_part, total_part])
    seq = _get(fields, "seq", int)
    total = _get(fields, "total", int)
    if len(payload) != total:
        raise PacketError(f"DATA seq={seq}: payload com {len(payload)} bytes, "
                          f"esperado total={total}")
    return Data(seq=seq, payload=payload)


def _parse_ok(fields):
    return Ok(
        file_size=_get(fields, "file_size", int),
        checksum=_get(fields, "checksum"),
        seed=_get(fields, "seed"),
        total_segments=_get(fields, "total_segments", int),
        segment_size=_get(fields, "segment_size", int),
    )


def _parse_done(fields):
    ok = _get(fields, "ok")
    if ok not in ("0", "1"):
        raise PacketError(f"DONE com ok inválido: {ok!r}")
    return Done(ok=ok == "1")


TEXT_PARSERS = {
    b"OK": _parse_ok,
    b"DONE": _parse_done,
    b"PONG": lambda fields: Pong(time=_get(fields, "time", float)),
    b"ERROR": lambda fields: Error(msg=_get(fields, "msg")),
}


def parse(packet):
    """Interpreta um datagrama recebido e devolve Ok, Data, Done, Pong ou Error.

    Lança PacketError se o pacote não segue o formato do protocolo.
    """
    kind = packet.split(SEP, 1)[0]
    if kind == b"DATA":
        return _parse_data(packet)
    if kind not in TEXT_PARSERS:
        raise PacketError(f"tipo de pacote desconhecido: {kind[:20]!r}")
    fields = _fields(packet.split(SEP)[1:])
    return TEXT_PARSERS[kind](fields)

# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

DEFAULT_MAX_RETRIES = 10
RECV_BUFFER = 65535


class DownloadError(Exception):
    """A transferência não pôde ser concluída.

    `segments` guarda as métricas dos segmentos recebidos antes da falha, para
    que o CSV da sessão seja gravado mesmo quando o download não termina.
    """

    def __init__(self, message, segments=()):
        super().__init__(message)
        self.segments = list(segments)


@dataclass(frozen=True)
class SegmentStats:
    """Métricas de um segmento, base de uma linha do CSV."""
    seq: int
    received_at: float     # time.time() na chegada do DATA (mesmo relógio do Wireshark)
    size_bytes: int
    rtt_ms: float          # do último REQ enviado até o DATA; None se houve retransmissão
    retransmissions: int   # REQs reenviados por timeout
    rtt_estimated_ms: float = None  # EWMA após este segmento (None: sem amostra)
    timeout_ms: float = None        # timeout em vigor para este segmento
    elapsed_ms: float = None        # do primeiro REQ até o DATA (inclui timeouts)
    loss_simulated: bool = False    # alguma perda deste segmento foi simulada

    @property
    def timeout_occurred(self):
        return self.retransmissions > 0

    @property
    def throughput_kbps(self):
        """Vazão do segmento em kbit/s: bits do payload / tempo total gasto.

        Usa `elapsed_ms` (que inclui timeouts) para que perdas apareçam como
        queda de vazão. bits/ms equivale a kbit/s (k = 1000).
        """
        elapsed = self.elapsed_ms if self.elapsed_ms is not None else self.rtt_ms
        if not elapsed or elapsed <= 0:
            return None
        return self.size_bytes * 8 / elapsed


@dataclass(frozen=True)
class Download:
    content: bytes
    segments: list
    spurious: int = 0  # retransmissões que se mostraram desnecessárias (só SR)

    @property
    def retransmissions(self):
        return sum(s.retransmissions for s in self.segments)

