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

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": [
        "settings_read",
        "tournament_write",
        "member_write",
        "education_write",
        "finance_write",
        "settings_write",
        "delete_records",
    ],
    "arbiter": [
        "settings_read",
        "tournament_write",
        "member_write",
    ],
    "teacher": [
        "settings_read",
        "education_write",
        "member_write",
    ],
    "assistant": [
        "settings_read",
        "member_write",
        "finance_write", # Básico
    ],
    "viewer": [
        "settings_read",
    ]
}

def get_permissions_for_role(role: str) -> list[str]:
    """Retorna a lista de permissões para a role informada."""
    return ROLE_PERMISSIONS.get(role, [])
