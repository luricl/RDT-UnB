## Timeout fixo vs adaptativo

SR, janela 16, arquivo `large`, seed 42, servidor real em 10/11/2026. Para
cada perda, as duas execuções rodaram em seguida (coluna `inicio`), com o
mesmo comando a menos do `--adaptive`:

    python3 cliente.py --server 137.131.178.229 --group grupo07 --file large \
      --protocol sr --window 16 --timeout 1000 [--adaptive] --loss <perda> --seed 42

O adaptativo usa α = 0,125, β = 0,25, piso de 50 ms, backoff e detecção de
retransmissão espúria (DATA duplicado).

- Com 5% e 10% de perda, o adaptativo termina ~10× mais rápido com o mesmo
  número de retransmissões: cada perda custa ~50 ms em vez de 1000 ms.
- Sem perda, o fixo nunca dispara e não paga nada; a diferença de tempo vem
  da rede (RTT mediano 32,6 ms na execução adaptativa e 25,6 ms na fixa). As
  49 retransmissões do adaptativo foram todas detectadas como espúrias.
