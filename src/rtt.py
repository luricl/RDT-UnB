"""Estimativa de RTT e timeout adaptativo, Kurose seção 3.5.3.

    EstimatedRTT = (1 - alpha) * EstimatedRTT + alpha * SampleRTT
    DevRTT       = (1 - beta)  * DevRTT      + beta  * |SampleRTT - EstimatedRTT|
    Timeout      = max(MinTimeout, EstimatedRTT + 4 * DevRTT)

Só amostras de segmentos sem retransmissão devem ser passadas a `update`
(algoritmo de Karn): numa retransmissão não dá para saber a qual REQ o DATA
responde. Esse filtro é feito por quem chama (ver `sr.segment_stats`).

O piso `min_timeout_ms` existe porque o filtro de Karn tem um efeito colateral:
um segmento lento estoura o timer, é retransmitido e sua amostra é descartada.
Sem piso, só as amostras rápidas sobrevivem, o DevRTT encolhe e o timeout cola
no RTT, gerando timeouts espúrios em cadeia. O TCP faz o mesmo (RFC 6298, 2.4).
"""

DEFAULT_ALPHA = 0.125  # valor recomendado pela RFC 6298 e pelo Kurose
DEFAULT_BETA = 0.25    # idem
DEFAULT_MIN_TIMEOUT_MS = 50.0  # acima do p99 do RTT medido (~40 ms); ver relatório da Entrega 3
DEVIATION_FACTOR = 4
MAX_TIMEOUT_MS = 60_000  # teto do backoff, RFC 6298 (2.5)


class RttEstimator:
    def __init__(self, alpha=DEFAULT_ALPHA, beta=DEFAULT_BETA,
                 min_timeout_ms=0.0):
        if not 0 < alpha <= 1:
            raise ValueError(f"alpha deve estar em (0, 1]: {alpha!r}")
        if not 0 < beta <= 1:
            raise ValueError(f"beta deve estar em (0, 1]: {beta!r}")
        if min_timeout_ms < 0:
            raise ValueError(f"min_timeout_ms deve ser >= 0: {min_timeout_ms!r}")
        self.alpha = alpha
        self.beta = beta
        self.min_timeout_ms = min_timeout_ms
        self.estimated_ms = None  # None até a primeira amostra válida
        self.dev_ms = None

    def update(self, sample_ms):
        """Incorpora uma amostra de RTT e devolve a nova estimativa."""
        if self.estimated_ms is None:
            # Primeira amostra: não há histórico para ponderar. DevRTT parte
            # de sample/2, como na RFC 6298.
            self.estimated_ms = sample_ms
            self.dev_ms = sample_ms / 2
        else:
            # DevRTT usa a estimativa anterior, antes de ela ser atualizada.
            self.dev_ms = ((1 - self.beta) * self.dev_ms
                           + self.beta * abs(sample_ms - self.estimated_ms))
            self.estimated_ms = ((1 - self.alpha) * self.estimated_ms
                                 + self.alpha * sample_ms)
        return self.estimated_ms

    def timeout_ms(self, fallback_ms):
        """Timeout atual; `fallback_ms` enquanto não houver amostra."""
        if self.estimated_ms is None:
            return fallback_ms
        return max(self.min_timeout_ms,
                   self.estimated_ms + DEVIATION_FACTOR * self.dev_ms)
