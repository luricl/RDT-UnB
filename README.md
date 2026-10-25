# RDT-UnB

Projeto final de TR2: transferência confiável de dados (RDT) sobre UDP, com o
protocolo RDT-UnB v1.0. O cliente implementa Stop-and-Wait, Go-Back-N e
Selective Repeat, com RTT adaptativo e coleta de métricas em CSV.

Restrições: apenas socket UDP nativo (`SOCK_DGRAM`), sem TCP e sem bibliotecas
de RDT prontas; o protocolo RDT-UnB v1.0 não pode ser alterado.

## Estrutura

```
cliente.py   ponto de entrada (CLI)
src/         código do cliente
tests/       testes unitários
data/        arquivos baixados
results/     CSVs de métricas e gráficos
captures/    capturas do Wireshark (.pcapng)
report/      relatório final
```

## Requisitos

Python 3 (testado com 3.12). Só biblioteca padrão por enquanto.

## Como executar

```
python3 cliente.py --server 137.131.178.229 --group grupo07 --file small
```

`--group` é obrigatório: sem ele o cliente encerra com erro.

| Opção | Descrição | Padrão |
|---|---|---|
| `--server` | IP ou hostname do servidor (obrigatório) | |
| `--port` | porta UDP do servidor | `8080` |
| `--group` | id do grupo, ex.: `grupo07` (obrigatório) | |
| `--file` | `small`, `medium` ou `large` | `small` |
| `--protocol` | `saw`, `gbn` ou `sr` | `saw` |
| `--window` | tamanho da janela (gbn/sr); `saw` usa sempre 1 | `4` para gbn/sr |
| `--segment-size` | `segment_size` solicitado, em bytes | `512` |
| `--loss` | probabilidade de perda simulada, de 0 a 1 | `0` (desligada) |
| `--timeout` | timeout de retransmissão, em milissegundos | `1000` |

`python3 cliente.py --help` mostra todas as opções.

## Métricas (CSV)

Ao fim de cada sessão — com sucesso ou com erro — o cliente grava
`results/metrics_<grupo>_<protocolo>_<YYYYMMDD_HHMMSS>.csv`, com uma linha por
segmento recebido. O horário do nome é o início da sessão.

| Coluna | Significado |
|---|---|
| `segment` | número de sequência |
| `timestamp` | chegada do DATA, ISO 8601 com fuso, relógio do sistema (o mesmo do Wireshark) |
| `size_bytes` | tamanho do payload |
| `rtt_ms` | último REQ enviado → DATA recebido |
| `rtt_estimated_ms` | EstimatedRTT por EWMA (α = 0,125); só amostras sem retransmissão entram (Karn); vazio até a primeira amostra |
| `timeout_ms` | timeout em vigor para o segmento |
| `throughput_kbps` | `size_bytes * 8 / tempo total do segmento`, em kbit/s; o tempo inclui timeouts, então perdas derrubam a vazão |
| `retransmissions` | REQs reenviados |
| `timeout_occurred` | 1 se houve timeout, senão 0 |
| `window_size` | 1 no SAW |
| `protocol` | `saw`, `gbn` ou `sr` |
| `loss_simulated` | 1 se alguma perda do segmento foi simulada pelo cliente (`--loss`), senão 0 |

## Entrega 2: comparação SAW × GBN × SR

Requer `pip install matplotlib`. Na raiz do repositório:

```
python scripts/entrega02_executa.py --server 137.131.178.229 --group grupo07
python scripts/entrega02_analisa.py
```

O primeiro comando roda os 21 cenários (SAW; GBN e SR com janela 4, 8 e 16;
perdas de 0, 5 e 10%) com o arquivo `small` e guarda CSVs, logs e
`execucoes.json` em `results/entrega02/`. Se for interrompido, rode de novo:
os cenários já concluídos são pulados. O segundo comando gera as tabelas, os
gráficos e o texto da análise em `report/gerado/` e `report/figuras/`, usados
por `report/entrega02.tex`.

A perda simulada (`--loss P --seed S`) descarta cada `DATA` recebido com
probabilidade P. Na demonstração ao vivo, rode sem `--loss`.

## Testes

```
python3 -m unittest
```
