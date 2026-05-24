from src.services.constants import OPERATOR_ROLES

# Matriz de Permissões
# Mapeia cada role para uma lista de permissões que ela possui.
# As permissões principais são:
# - tournament_write: Criar/Editar/Apagar torneios e rodadas
# - member_write: Cadastrar/Editar membros (mas não deletar globalmente)
# - education_write: Criar aulas, exercícios e gerenciar apostilas
# - finance_write: Gerenciar receitas/despesas
# - settings_write: Alterar configs de segurança/clube
# - delete_records: Permissão global para apagar registros definitivamente

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": [
        "tournament_write",
        "member_write",
        "education_write",
        "finance_write",
        "settings_write",
        "delete_records",
    ],
    "arbiter": [
        "tournament_write",
        "member_write",
    ],
    "teacher": [
        "education_write",
        "member_write",
    ],
    "assistant": [
        "member_write",
        "finance_write", # Básico
    ],
    "viewer": [
        # Apenas consulta, sem permissões de escrita
    ]
}

def get_permissions_for_role(role: str) -> list[str]:
    """Retorna a lista de permissões para a role informada."""
    return ROLE_PERMISSIONS.get(role, [])
