"""Pacote pairing — submódulos com funções puras de pareamento/desempate.

Spec §6.1 sugere a estrutura abaixo. Esta é uma extração incremental:
movemos para cá apenas as funções **puras** (sem dependência de Database),
deixando PairingService intacto em src/services/pairing_service.py como
facade. Os módulos crescem por extração quando uma função se prova
isolável.

Estrutura alvo (spec §6.1):

    pairing/
      __init__.py
      models.py          # dataclasses de entrada/saída              (futuro)
      fide_dutch.py      # algoritmo principal Swiss individual      (futuro)
      team_swiss.py      # pareamento por equipes                    (futuro)
      constraints.py     # restrições absolutas e preferências       (futuro)
      explain.py         # explicações de decisão                    (futuro)
      validators.py      # checagens antes/depois                    (futuro)
      snapshots.py       # serialização do input/output              (futuro)
      result_states.py   # ✓ ciclo de vida do resultado (extraído)
      tiebreaks.py       # ✓ componentes de tiebreak (extraído)

Para extrair uma nova função:
  1. confirme que ela é pura (não usa self.db, não muta estado externo);
  2. mova para o módulo apropriado como função top-level;
  3. mantenha em PairingService um alias chamando a função (ou re-export
     via método estático) para preservar a API pública.
"""

from src.services.pairing.acceleration import (
    accelerated_standings,
    classic_acceleration_bonus,
    classic_upper_half_size,
)
from src.services.pairing.arbitration import (
    acknowledged_issue_keys,
    audit_issue,
    blocking_issues_message,
    clock_event_issue,
    clock_issue,
    finalize_issues,
    issue_matches_round,
    issue_metrics,
    individual_round_dashboard_metrics,
    result_submission_issue,
    team_round_dashboard_metrics,
)
from src.services.pairing.constraints import (
    assignment_color_penalty,
    choose_bye_player,
    choose_colors,
    choose_team_bye,
    choose_team_colors,
    float_penalty,
    greedy_player_pairs,
    greedy_team_pairs,
    is_color_valid_fide,
    optimal_player_pairs,
    optimal_team_pairs,
    pair_penalty,
    pairing_order_key,
    rank_by_player_id,
    team_pair_penalty,
    team_pairing_order_key,
    would_make_three_colors,
)
from src.services.pairing.fide_dutch import (
    dutch_bracket_pairing,
    first_round_pairings,
    knockout_pairings,
    round_robin_pairings,
    score_groups,
    search_dutch_pairing,
    swiss_pairings,
)
from src.services.pairing.histories import (
    bye_player_ids,
    color_histories,
    float_histories,
    played_pairs,
    team_bye_ids,
    team_color_histories,
    team_played_pairs,
)
from src.services.pairing.previews import individual_preview_payload, team_preview_payload
from src.services.pairing.prohibitions import (
    prohibited_pairs_for_round,
    prohibition_applies,
)
from src.services.pairing.result_states import derive_pairing_state, result_states_summary
from src.services.pairing.snapshots import pairing_input_snapshot
from src.services.pairing.team_swiss import (
    dutch_team_bracket_pairing,
    first_round_team_matches,
    search_dutch_team_pairing,
    swiss_team_matches,
    team_bye_payload,
    team_bye_summary,
    team_match_payload,
    team_match_summary,
    team_starter_roster,
)
from src.services.pairing.tiebreaks import (
    calculate_player_standings,
    calculate_team_standings,
    flatten_tiebreak_components,
    order_player_standings,
    performance_components,
    performance_rating,
    player_tiebreak_components,
    team_standing_value,
    tiebreak_narrative_from_standings,
)
from src.services.pairing.validators import (
    find_player_slot,
    find_team_board_player_slot,
    plan_pairing_player_swap,
    plan_team_board_player_swap,
)

__all__ = [
    "accelerated_standings",
    "acknowledged_issue_keys",
    "assignment_color_penalty",
    "classic_acceleration_bonus",
    "classic_upper_half_size",
    "audit_issue",
    "blocking_issues_message",
    "bye_player_ids",
    "clock_event_issue",
    "finalize_issues",
    "calculate_player_standings",
    "calculate_team_standings",
    "choose_bye_player",
    "choose_colors",
    "choose_team_bye",
    "choose_team_colors",
    "clock_issue",
    "color_histories",
    "derive_pairing_state",
    "dutch_bracket_pairing",
    "dutch_team_bracket_pairing",
    "find_player_slot",
    "find_team_board_player_slot",
    "flatten_tiebreak_components",
    "float_histories",
    "float_penalty",
    "first_round_pairings",
    "first_round_team_matches",
    "greedy_player_pairs",
    "greedy_team_pairs",
    "is_color_valid_fide",
    "issue_matches_round",
    "issue_metrics",
    "knockout_pairings",
    "individual_preview_payload",
    "individual_round_dashboard_metrics",
    "optimal_player_pairs",
    "optimal_team_pairs",
    "order_player_standings",
    "pair_penalty",
    "pairing_order_key",
    "pairing_input_snapshot",
    "plan_pairing_player_swap",
    "plan_team_board_player_swap",
    "played_pairs",
    "prohibited_pairs_for_round",
    "prohibition_applies",
    "performance_components",
    "performance_rating",
    "player_tiebreak_components",
    "rank_by_player_id",
    "result_submission_issue",
    "result_states_summary",
    "round_robin_pairings",
    "score_groups",
    "search_dutch_pairing",
    "search_dutch_team_pairing",
    "swiss_pairings",
    "swiss_team_matches",
    "team_bye_payload",
    "team_bye_summary",
    "team_bye_ids",
    "team_color_histories",
    "team_match_payload",
    "team_match_summary",
    "team_starter_roster",
    "team_pair_penalty",
    "team_pairing_order_key",
    "team_preview_payload",
    "team_played_pairs",
    "team_round_dashboard_metrics",
    "team_standing_value",
    "tiebreak_narrative_from_standings",
    "would_make_three_colors",
]
