## Comparação de α e β por reprodução do traço de RTT

Gerado por `python3 scripts/ewma_replay.py results/entrega03/ewma_replay/resumo.csv \
results/entrega03/timeout_fixo_vs_adaptativo/p{00,05,10}_fixo.csv \
results/entrega01/execucoes/large/*.csv`.

Na rede real o RTT mediano variou de 26 a 93 ms na mesma tarde (ver
`../ewma_piso50`), então o tempo de cada execução depende mais da rede do que
do par α/β. Aqui todos os pares recebem a mesma sequência de RTTs, tirada de
execuções com timeout fixo de 1000 ms (nenhuma amostra cortada). A última
linha de traços é sintética: o primeiro traço com +100 ms a partir da metade.

Resultado, no traço `p00_fixo` sem piso e no degrau com piso de 50 ms:

| α / β | espúrios (rede estável) | amostras até seguir o degrau | espúrios após o degrau |
|---|---|---|---|
| 0,05 / 0,25 | 264 | 39 | 1 |
| **0,125 / 0,25** | **334** | **14** | **1** |
| 0,25 / 0,25 | 425 | 7 | 2 |
| 0,5 / 0,25 | 624 | 4 | 2 |
| 0,125 / 0,1 | 399 | 14 | 3 |
| 0,125 / 0,5 | 408 | 14 | 1 |
| 1 / 1 | 2 615 | 1 | 7 |

α pequeno filtra melhor o ruído, mas demora a seguir uma subida do RTT; α
grande segue rápido, mas o timeout passa a imitar o ruído. β = 0,25 teve
menos espúrios que 0,1 e 0,5 nos três traços desta entrega (no da Entrega 1,
β = 0,1 ganhou: 627 contra 718) e reage logo ao degrau, enquanto β = 0,1
deixa passar 3 espúrios. Os valores da RFC 6298 (0,125 / 0,25) ficam no equilíbrio, e são
os usados pelo cliente. Com o piso de 50 ms, os traços estáveis quase não
geram espúrios com nenhum par: o piso domina enquanto o RTT está baixo.
