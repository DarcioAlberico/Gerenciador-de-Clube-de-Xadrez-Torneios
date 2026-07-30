"""Tela de Rodadas na camada de UI.

Quarta tela-monstro migrada pela **B-6** (1.850 linhas num arquivo só),
seguindo o molde do piloto de Árbitros (F1.5) e a lição das telas de Jogadores
e Arbitragem: quando o arquivo **é** várias telas, o pacote ganha um módulo por
tela em vez de espremer tudo em três camadas.

- [`state.py`](state.py) — dado puro: em que estado está um resultado, que
  resultado a mesa aceita, quantas rodadas o torneio deveria ter, como se lê a
  prévia e como o projetor pagina;
- [`view.py`](view.py) — o mixin: barra da rodada, tabela de mesas e
  lançamento de resultado, que é o que a tela **é**;
- [`initial_call.py`](initial_call.py) — a chamada inicial, que é a *outra*
  tela: antes da primeira rodada não há rodada para editar;
- [`projector.py`](projector.py) — o Modo Projetor, uma tela inteira com
  cores próprias, alheias ao tema (quem vê é a sala, na parede);
- [`exports.py`](exports.py) — as cinco exportações/impressões da rodada;
- [`qr.py`](qr.py) — resultado por QR: link da mesa, servidor local e fila de
  aprovação (nada entra sem o árbitro aprovar);
- [`swaps.py`](swaps.py) — inverter cores e substituir jogador na mesa.

O import externo continua o mesmo (``from .pairing_results import
PairingResultsMixin``).
"""
from __future__ import annotations

from .view import PairingResultsMixin

__all__ = ["PairingResultsMixin"]
