## Comparação de α e β por reprodução do traço de RTT

Gerado por `python3 scripts/ewma_replay.py results/entrega03/ewma_replay/resumo.csv \
results/entrega03/timeout_fixo_vs_adaptativo/p{00,05,10}_fixo.csv \
results/entrega01/execucoes/large/*.csv`.

Na rede real o RTT mediano variou de 26 a 93 ms na mesma tarde (ver
`../ewma_piso50`), então o tempo de cada execução depende mais da rede do que
do par α/β. Aqui todos os pares recebem a mesma sequência de RTTs, tirada de
execuções com timeout fixo de 1000 ms (nenhuma amostra cortada). A última
linha de traços é sintética ("pulso"): o primeiro traço com +100 ms no terço
do meio, como um atraso ligado e depois desligado.

Resultado no traço `p00_fixo` (sem piso) e no pulso (com piso de 50 ms):

| α / β | espúrios, rede estável | espúrios nas 100 amostras após a subida | amostras até seguir a subida | timeout médio após o atraso sumir (RTT ~26 ms) |
|---|---|---|---|---|
| 0,05 / 0,25 | 265 | 1 | 44 | 131 ms |
| 0,125 / 0,25 | 334 | 3 | 17 | 82 ms |
| 0,25 / 0,25 | 425 | 3 | 8 | 66 ms |
| 0,5 / 0,25 | 624 | 4 | 4 | 58 ms |
| 0,125 / 0,1 | 398 | 3 | 17 | 79 ms |
| 0,125 / 0,5 | 409 | 4 | 17 | 84 ms |
| 1 / 1 | 2 614 | 13 | 1 | 56 ms |

- α pequeno filtra melhor o ruído: α = 0,05 teve ~20% menos espúrios em todos
  os traços estáveis (265 contra 334 aqui; 640 contra 718 no da Entrega 1) e
  também menos logo depois da subida.
- O custo aparece quando o atraso some: o EstimatedRTT demora a descer e o
  timeout fica alto (131 ms contra 82 ms), então cada perda nesse trecho custa
  ~1,6× mais. α grande desce rápido, mas o timeout passa a imitar o ruído.
- β = 0,25 teve menos espúrios que 0,1 e 0,5 nos três traços desta entrega
  (no da Entrega 1, β = 0,1 ganhou: 627 contra 718).
- Com o piso de 50 ms, os traços estáveis quase não geram espúrios com nenhum
  par: o piso domina enquanto o RTT está baixo.

A escolha fica entre 0,05 (menos espúrios com rede estável) e 0,125, o valor
da RFC 6298 (volta mais rápido depois de um atraso passageiro). O cliente
usa 0,125 / 0,25 por padrão; ambos podem ser passados com `--alpha`/`--beta`.
