"""Telas de arbitragem na camada de UI.

Terceira tela-monstro migrada pela **B-6** (1.527 linhas num arquivo só),
seguindo o molde do piloto de Árbitros (F1.5) e a lição da tela de Jogadores:
quando o arquivo **é** várias telas, o pacote ganha um módulo por tela em vez de
espremer tudo em três camadas.

- [`state.py`](state.py) — dado puro: cartões, próximo passo, validação dos três
  cadastros TRF25, parsing de pontos e rodadas;
- [`controller.py`](controller.py) — decide e fala com banco/serviços, sem Tk,
  e é onde a escolha entre individual e equipes fica explícita;
- [`panel.py`](panel.py) — o painel do árbitro, e
  [`pending.py`](pending.py) — as mesas aguardando resultado, que é a parte do
  painel que o árbitro **usa** (as outras informam);
- [`issues.py`](issues.py) — a Central de pendências;
- [`registry.py`](registry.py) + [`page.py`](page.py) — a casca comum dos três
  cadastros TRF25, e o contrato que cada um cumpre;
- [`adjustments.py`](adjustments.py), [`byes.py`](byes.py),
  [`prohibitions.py`](prohibitions.py) — o que cada cadastro tem de próprio;
- [`checklist.py`](checklist.py) — o diálogo que precede o fechamento da rodada;
- [`exports.py`](exports.py) — as seis publicações que o painel dispara;
- [`refresh.py`](refresh.py) — a auto-atualização e suas preferências;
- [`view.py`](view.py) — o mixin, agora uma casca fina.

O import externo continua o mesmo (``from .pairing_arbitration import
ArbitrationPagesMixin``).
"""
from __future__ import annotations

from .view import ArbitrationPagesMixin

__all__ = ["ArbitrationPagesMixin"]
