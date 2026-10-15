"""Estimativa de RTT por média móvel exponencial (EWMA), Kurose seção 3.5.3.

    EstimatedRTT = (1 - alpha) * EstimatedRTT + alpha * SampleRTT

Na Entrega 1 (SAW) o timeout continua fixo; o estimador só alimenta a coluna
`rtt_estimated_ms` do CSV. Nas próximas entregas ele passa a definir o timeout.
"""

DEFAULT_ALPHA = 0.125  # valor recomendado pela RFC 6298 e pelo Kurose


class RttEstimator:
    def __init__(self, alpha=DEFAULT_ALPHA):
        if not 0 < alpha <= 1:
            raise ValueError(f"alpha deve estar em (0, 1]: {alpha!r}")
        self.alpha = alpha
        self.estimated_ms = None  # None até a primeira amostra válida

    def update(self, sample_ms):
        """Incorpora uma amostra de RTT e devolve a nova estimativa."""
        if self.estimated_ms is None:
            # Primeira amostra: não há histórico para ponderar.
            self.estimated_ms = sample_ms
        else:
            self.estimated_ms = ((1 - self.alpha) * self.estimated_ms
                                 + self.alpha * sample_ms)
        return self.estimated_ms
