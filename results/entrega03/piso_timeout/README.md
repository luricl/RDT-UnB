## Piso do timeout adaptativo

SR, janela 16, arquivo `large`, `--adaptive` com α = 0,125 e β = 0,25, seed 42,
servidor real em 10/11/2026. Varia só o `--min-timeout` (0, 50, 100 e 200 ms),
sem e com 10% de perda simulada. O piso 0 equivale a ter só o backoff.

Comando de cada execução:

    python3 cliente.py --server 137.131.178.229 --group grupo07 --file large \
      --protocol sr --window 16 --adaptive --min-timeout <piso> --loss <perda> --seed 42

- `p<perda>_min<piso>.csv`: métricas por segmento; `logs/`: saída do cliente.
- `resumo.csv`: uma linha por execução. `retransmissoes_extras` é
  retransmissões − segmentos com perda simulada: sem perda, todas são espúrias;
  com perda, inclui também segmentos perdidos mais de uma vez.

Sem o piso, o timeout fica colado no RTT (~28 ms) e há milhares de
retransmissões espúrias. Com 50 ms elas praticamente somem (16 em 20 480
segmentos) e, sob perda, o tempo total cresce com o piso, porque cada perda
custa cerca de um timeout. Por isso o padrão do cliente é 50 ms.

Essas execuções usam o código só com piso e backoff (commit `af77435`), sem a
detecção de retransmissão espúria. `p00_min50_rede_lenta.csv` é a mesma
configuração de `p00_min50.csv`, rodada ~20 min depois, com a rede mais lenta
(RTT mediano 34 ms, p99 84 ms): 8 951 retransmissões. Os segmentos acima de
50 ms estouravam o timer, suas amostras eram descartadas (Karn) e o estimador
nunca via o RTT subir. Isso motivou a detecção por DATA duplicado no `sr.py`.
