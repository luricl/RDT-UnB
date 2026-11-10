## Varredura de α e β na rede real (com piso)

`scripts/ewma_executa.py` (de Lurian) rodado de novo com o cliente final
(piso de 50 ms, backoff e detecção de retransmissão espúria):

    python3 scripts/ewma_executa.py --server 137.131.178.229 --group grupo07 \
      --file large --timeout 80 --out results/entrega03/ewma_piso50 --losses 0.0 0.1

Atenção: entre 17h29 e 17h35 a rede ficou bem mais lenta (RTT mediano de
83 a 93 ms, contra ~26 ms no resto), o que pegou os pares 0,25/0,25,
0,5/0,25 e 0,125/0,1 sem perda e alguns com perda. Com uma execução por par,
o tempo total aqui mede mais a rede do que o par. A comparação controlada
está em `../ewma_replay`.
