# Fixtures de torneios

Cenários reproduzíveis para testes de regressão (spec §15.2).

## Como usar

```python
from tests.fixtures import load_tournament_fixture

tournament_id = load_tournament_fixture(
    "individual_8_players_3_rounds", self.db, self.service
)
```

`load_tournament_fixture(name, db, pairing_service)` cria o torneio, jogadores,
gera/fecha as rodadas conforme a fixture, e devolve o `tournament_id`.

## Como adicionar um cenário

1. Crie `<nome>.json` neste diretório seguindo o schema documentado em
   [`../loader.py`](../loader.py).
2. Use ratings decrescentes (2000, 1950, ...) para resultados deterministas
   do emparceiramento Swiss.
3. Em `results_by_board`, declare somente as mesas que devem ter resultado.
   Mesas omitidas ficam vazias.
4. Use `"close": false` em uma rodada se quiser deixá-la aberta no fim do
   carregamento (útil para testar fluxo de pendências).
5. Adicione um teste em `tests/test_core_services.py` que carregue a fixture
   e assereja propriedades-chave do estado resultante.

## Cenários atuais

| Nome | Descrição |
|---|---|
| `individual_8_players_3_rounds` | Swiss individual completo, gera empate de pontos no topo da classificação para exercitar critérios de desempate. |

## Cenários sugeridos pela spec (a implementar)

- `individual_9_players_bye` — número ímpar exercita atribuição de bye
- `individual_color_conflict` — força sequência que dispare alertas de cor
- `team_6_teams_4_boards` — torneio por equipes com 4 tabuleiros
- `team_substitution_case` — escalação com substituição auditada
- `late_entry_case` — jogador entrando após rodada 2
- `withdrawn_player_case` — desistência no meio do torneio
- `corrected_result_case` — resultado alterado após rodada fechada
