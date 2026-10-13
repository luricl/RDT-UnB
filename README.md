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
python3 cliente.py --server 137.131.178.229 --group grupo01 --file small
```

`--group` é obrigatório: sem ele o cliente encerra com erro.

| Opção | Descrição | Padrão |
|---|---|---|
| `--server` | IP ou hostname do servidor (obrigatório) | |
| `--port` | porta UDP do servidor | `8080` |
| `--group` | id do grupo, ex.: `grupo01` (obrigatório) | |
| `--file` | `small`, `medium` ou `large` | `small` |
| `--protocol` | `saw`, `gbn` ou `sr` | `saw` |
| `--window` | tamanho da janela (gbn/sr); `saw` usa sempre 1 | `4` para gbn/sr |
| `--segment-size` | `segment_size` solicitado, em bytes | `512` |
| `--loss` | probabilidade de perda simulada, de 0 a 1 | `0` (desligada) |
| `--timeout` | timeout de retransmissão, em milissegundos | `1000` |

`python3 cliente.py --help` mostra todas as opções.

## Testes

```
python3 -m unittest
```
