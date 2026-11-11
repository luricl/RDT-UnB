## Varredura de α e β na rede real: segunda rodada

Mesmo comando e mesmo código de `../ewma_piso50`, rodado de novo entre
21h58 e 22h13 para testar se as diferenças de tempo vinham do par α/β ou
da rede:

    python3 scripts/ewma_executa.py --server 137.131.178.229 --group grupo07 \
      --file large --timeout 80 --out results/entrega03/ewma_piso50_rodada2 \
      --losses 0.0 0.1

### Rodada 1 x rodada 2

RTT mediano = mediana do `rtt_ms` de cada execução (só segmentos sem
retransmissão).

| Perda · α/β | Rodada 1: tempo | Rodada 1: RTT mediano | Rodada 2: tempo | Rodada 2: RTT mediano |
|---|---|---|---|---|
| 0% · 0,125/0,25 | 37,1 s | 26,1 ms | 42,3 s | 32,6 ms |
| 0% · 0,05/0,25 | 41,8 s | 29,9 ms | 33,3 s | 25,9 ms |
| 0% · 0,25/0,25 | 104,0 s | 93,5 ms | 33,3 s | 25,8 ms |
| 0% · 0,5/0,25 | 99,1 s | 90,8 ms | 34,9 s | 26,5 ms |
| 0% · 0,125/0,1 | 94,3 s | 83,5 ms | 37,7 s | 28,8 ms |
| 0% · 0,125/0,5 | 72,8 s | 34,2 ms | 37,2 s | 28,5 ms |
| 0% · 1/1 | 96,8 s | 43,7 ms | 35,5 s | 27,1 ms |
| 10% · 0,125/0,25 | 223,6 s | 50,1 ms | 92,7 s | 26,6 ms |
| 10% · 0,05/0,25 | 111,0 s | 28,2 ms | 100,5 s | 30,7 ms |
| 10% · 0,25/0,25 | 92,9 s | 26,5 ms | 96,4 s | 27,7 ms |
| 10% · 0,5/0,25 | 91,4 s | 26,2 ms | 93,5 s | 27,7 ms |
| 10% · 0,125/0,1 | 99,6 s | 32,9 ms | 93,4 s | 27,6 ms |
| 10% · 0,125/0,5 | 128,7 s | 26,9 ms | 92,2 s | 26,6 ms |
| 10% · 1/1 | 112,7 s | 26,3 ms | 93,8 s | 27,6 ms |

### Conclusão

- O tempo acompanha o RTT da rede na hora da execução, não o par. A ordem
  dos pares muda entre as rodadas. Por exemplo, 0,125/0,25 sem perda foi o
  mais rápido na rodada 1 e o mais lento na rodada 2 (RTT mediano de
  32,6 ms). Com 10% de perda, o pior da rodada 2 foi o 0,05/0,25, também a
  execução com a rede mais lenta (30,7 ms).
- Com a rede estável (rodada 2), todos os pares ficaram entre 33 e 42 s sem
  perda e entre 92 e 101 s com 10%. O timeout médio ficou entre 50 e 59 ms,
  colado no piso, como o replay em `../ewma_replay` previu.
- Com 10% de perda e seed 42, o cliente descarta exatamente 2267 DATA. Na
  rodada 2 os pares ficaram entre 2267 retransmissões (nenhuma espúria) e
  2443 (176 espúrias).
- Uma execução por par na rede real não serve para escolher α e β: a
  variação da rede (RTT mediano de 26 a 93 ms) é bem maior que o efeito do
  par. A escolha de α = 0,125 e β = 0,25 se apoia no replay sobre o mesmo
  traço (`../ewma_replay`) e na RFC 6298.
