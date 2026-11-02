"""Estimativa de RTT e timeout adaptativo, Kurose seção 3.5.3.

    EstimatedRTT = (1 - alpha) * EstimatedRTT + alpha * SampleRTT
    DevRTT       = (1 - beta)  * DevRTT      + beta  * |SampleRTT - EstimatedRTT|
    Timeout      = EstimatedRTT + 4 * DevRTT

Só amostras de segmentos sem retransmissão devem ser passadas a `update`
(algoritmo de Karn): numa retransmissão não dá para saber a qual REQ o DATA
responde. Esse filtro é feito por quem chama (ver `sr.segment_stats`).
"""

DEFAULT_ALPHA = 0.125  # valor recomendado pela RFC 6298 e pelo Kurose
DEFAULT_BETA = 0.25    # idem
DEVIATION_FACTOR = 4


class RttEstimator:
    def __init__(self, alpha=DEFAULT_ALPHA, beta=DEFAULT_BETA):
        if not 0 < alpha <= 1:
            raise ValueError(f"alpha deve estar em (0, 1]: {alpha!r}")
        if not 0 < beta <= 1:
            raise ValueError(f"beta deve estar em (0, 1]: {beta!r}")
        self.alpha = alpha
        self.beta = beta
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
        return self.estimated_ms + DEVIATION_FACTOR * self.dev_ms
