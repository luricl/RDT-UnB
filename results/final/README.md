## Campanha final (15/11/2026)

Todos os experimentos do relatório final, rodados numa única sessão com o
código final, contra o servidor 137.131.178.229:

    python3 scripts/final_executa.py --server 137.131.178.229 --group grupo07 --iface enp3s0
    python3 scripts/final_analisa.py

- `execucoes.csv`: um cenário por linha (configuração, CSV, MD5 calculado e
  esperado, resposta do DONE, retransmissões desnecessárias detectadas).
- `resumo.csv`: métricas de cada execução calculadas do CSV (tempo, vazão,
  retransmissões, RTT mediano, timeout médio do REQ original).
- `replay.csv`: pares α/β aplicados ao traço de RTT de `sr_fixo_p00`.
- `csv/`: CSVs de métricas, no padrão `metrics_grupo07_<protocolo>_<AAAAMMDD_HHMMSS>.csv`.
- `logs/`: saída do cliente de cada execução.
- `captura/sr_adapt_p05.pcapng.gz`: captura do Wireshark da execução
  `sr_adapt_p05` (SR, janela 16, adaptativo, 5% de perda, large).

Prefixos dos cenários: `sr_fixo`/`sr_adapt` (SR N=16 large, timeout fixo de
1000 ms ou adaptativo com piso de 50 ms), `sr_pisoX` (piso X ms), `sr_aA_bB`
(α e β), `gbn_fixo`, `saw_large`, `saw_medium`, `e2_<protocolo>_w<N>_p<perda>`
(Entrega 2, small; `e2_saw_w1_p00` é também o small da Entrega 1). O sufixo
`pXX` é a perda simulada em %.

Na hora da campanha a rede alternava blocos de 16 segmentos com RTT de ~33 ms
e ~65 ms; ver a Seção 2 do relatório.
