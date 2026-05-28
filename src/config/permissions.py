# Matriz de Permissões
# Mapeia cada role para uma lista de permissões que ela possui.
# As permissões principais são:
# - settings_read: Consultar configuracoes, comunicacao e auditoria
# - tournament_write: Criar/Editar/Apagar torneios e rodadas
# - member_write: Cadastrar/Editar membros (mas não deletar globalmente)
# - education_write: Criar aulas, exercícios e gerenciar apostilas
# - finance_write: Gerenciar receitas/despesas
# - settings_write: Alterar configs de segurança/clube
# - delete_records: Permissão global para apagar registros definitivamente
#
# Permissões adicionadas para perfis de torneio (spec §14.1):
# - team_lineup_submit: Capitão envia escalação da equipe
# - team_substitution_request: Capitão solicita substituição de jogador
# - own_data_read: Jogador consulta apenas dados próprios (escopo de UI/rota)
# - presence_confirm: Jogador confirma presença em torneio
#
# Nota sobre escopo: own_data_read e team_lineup_submit indicam INTENÇÃO da
# permissão. A restrição "apenas a própria equipe" ou "apenas o próprio
# jogador" deve ser aplicada na camada que consulta os dados (UI/rota),
# filtrando por user → member_id/team_id. Este módulo só decide se a ação
# é permitida pelo papel.

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": [
        "settings_read",
        "tournament_write",
        "member_write",
        "education_write",
        "finance_write",
        "settings_write",
        "delete_records",
        "team_lineup_submit",
        "team_substitution_request",
        "own_data_read",
        "presence_confirm",
    ],
    "arbiter": [
        "settings_read",
        "tournament_write",
        "member_write",
        "team_lineup_submit",
        "team_substitution_request",
    ],
    "teacher": [
        "settings_read",
        "education_write",
        "member_write",
    ],
    "assistant": [
        "settings_read",
        "member_write",
        "finance_write",  # Básico
    ],
    "viewer": [
        "settings_read",
    ],
    "capitao": [
        "team_lineup_submit",
        "team_substitution_request",
        "own_data_read",
    ],
    "jogador": [
        "own_data_read",
        "presence_confirm",
    ],
}

def get_permissions_for_role(role: str) -> list[str]:
    """Retorna a lista de permissões para a role informada."""
    return ROLE_PERMISSIONS.get(role, [])
