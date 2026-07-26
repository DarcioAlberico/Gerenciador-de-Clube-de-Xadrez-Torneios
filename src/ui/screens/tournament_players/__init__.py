"""Tela de Jogadores na camada de UI.

Segunda tela-monstro migrada pela **B-6** (1.613 linhas num arquivo só),
seguindo o molde do piloto de Árbitros (F1.5):

- [`state.py`](state.py) — dado puro: formulário, linha, resumo, busca, autofill;
- [`controller.py`](controller.py) — decide e fala com banco/serviços, sem Tk;
- [`view.py`](view.py) — monta widgets e faz a ponte;
- [`actions.py`](actions.py) — base das ações (torneio corrente, background, erro);
- [`imports.py`](imports.py) — planilha, inscrições online e mapeamento de colunas;
- [`forms.py`](forms.py) — formulário de inscrição no Google Forms;
- [`ratings.py`](ratings.py) — bases oficiais (FIDE/CBX/LBX/estrangeiras);
- [`chess_results.py`](chess_results.py) — ponte com o Chess-Results.com;
- [`dialogs.py`](dialogs.py) e [`file_types.py`](file_types.py) — casca dos
  modais e filtros de arquivo.

Os quatro módulos de ação existem porque a tela **é** quatro telas: cadastrar
jogador, importar de fora, cuidar de rating oficial e publicar. Deixá-las juntas
foi o que produziu o arquivo de 1.613 linhas.

O import externo continua o mesmo (`from .screens.tournament_players import
TournamentPlayersMixin`).
"""
from __future__ import annotations

from .view import TournamentPlayersMixin, TournamentPlayersView

__all__ = ["TournamentPlayersMixin", "TournamentPlayersView"]
