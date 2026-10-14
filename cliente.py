"""Ponto de entrada do cliente RDT-UnB.

Exemplo:
    python3 cliente.py --server 137.131.178.229 --group grupo07 --file small
"""

import sys

from src.cli import main

if __name__ == "__main__":
    sys.exit(main())
