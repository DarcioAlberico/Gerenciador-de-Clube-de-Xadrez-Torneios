"""Agrupamento das ações da tela de Jogadores (F5.6 / P3-7).

Vinte e cinco botões azuis idênticos, empilhados numa coluna de 280px, sem
separação nem hierarquia: era a tela mais usada no dia da inscrição e a que mais
desmentia a promessa de aplicativo profissional. A F2.1 já tinha provado o molde
na barra de Rodadas; aqui ele chega ao formulário.

O critério do agrupamento é **de onde o jogador vem**, que é a pergunta que o
operador realmente faz:

- avulso, digitado na hora → botões soltos no topo;
- do cadastro do clube ou de um formulário de inscrição → ``Inscrever``;
- de um arquivo/link que alguém mandou → ``Importar``;
- de uma base de rating oficial → ``Bases oficiais``.

Publicar é saída, não entrada, e fica solto. Excluir é destrutivo e fica isolado
no fim (``DangerAction``).

Módulo **puro**: recebe um mapa ``chave -> callable`` e devolve a estrutura. Não
importa Tk nem sabe desenhar — quem desenha é ``_grid_form_buttons``. Assim a
decisão de agrupamento, que é o que se discute e se revisa, tem teste sem janela.

Cada ``t()`` recebe uma **string literal**, nunca f-string: o ``test_ui_i18n``
varre as chamadas por AST, e chave montada em tempo de execução vira chave órfã
no catálogo (a mesma decisão de desenho tomada na B-3 para os títulos de coluna).
"""
from __future__ import annotations

from typing import Any, Callable, Mapping

from ...components import ActionGroup, DangerAction, FormAction
from ...i18n import t

Handlers = Mapping[str, Callable[[], Any]]

# As 25 ações da tela, por chave. Existe para o teste cobrar que o mapa de
# handlers e o agrupamento continuam falando da mesma lista — acrescentar uma
# ação e esquecer de exibi-la é o erro que este módulo torna possível.
ACTION_KEYS = (
    "add_guest",
    "update",
    "clear",
    "register_member",
    "register_all",
    "update_status",
    "generate_form",
    "configure_form",
    "share_form",
    "template_players",
    "template_online",
    "import_spreadsheet",
    "import_mapped",
    "import_mapped_url",
    "import_online",
    "import_online_url",
    "import_chess_results",
    "import_fide",
    "import_cbx",
    "import_lbx",
    "import_foreign",
    "update_lbx",
    "compare_official",
    "publish_chess_results",
    "delete",
)


def player_actions(h: Handlers) -> list[FormAction]:
    """As 25 ações da tela em 8 controles visíveis, na ordem de exibição."""
    return [
        # Entrada avulsa: o que o operador faz com o formulário ao lado aberto.
        (t("players.action.add_guest"), h["add_guest"]),
        (t("players.action.update"), h["update"]),
        (t("players.action.clear"), h["clear"]),
        ActionGroup(
            t("players.group.register"),
            [
                (t("players.action.register_member"), h["register_member"]),
                (t("players.action.register_all"), h["register_all"]),
                None,
                (t("players.action.update_status"), h["update_status"]),
                None,
                (t("players.action.generate_form"), h["generate_form"]),
                (t("players.action.configure_form"), h["configure_form"]),
                (t("players.action.share_form"), h["share_form"]),
            ],
            tip=t("players.group.register.tip"),
        ),
        ActionGroup(
            t("players.group.import"),
            [
                (t("players.action.template_players"), h["template_players"]),
                (t("players.action.template_online"), h["template_online"]),
                None,
                (t("players.action.import_spreadsheet"), h["import_spreadsheet"]),
                (t("players.action.import_mapped"), h["import_mapped"]),
                (t("players.action.import_mapped_url"), h["import_mapped_url"]),
                None,
                (t("players.action.import_online"), h["import_online"]),
                (t("players.action.import_online_url"), h["import_online_url"]),
                None,
                (t("players.action.import_chess_results"), h["import_chess_results"]),
            ],
            tip=t("players.group.import.tip"),
        ),
        ActionGroup(
            t("players.group.official"),
            [
                (t("players.action.import_fide"), h["import_fide"]),
                (t("players.action.import_cbx"), h["import_cbx"]),
                (t("players.action.import_lbx"), h["import_lbx"]),
                (t("players.action.import_foreign"), h["import_foreign"]),
                None,
                (t("players.action.update_lbx"), h["update_lbx"]),
                (t("players.action.compare_official"), h["compare_official"]),
            ],
            tip=t("players.group.official.tip"),
        ),
        (t("players.action.publish_chess_results"), h["publish_chess_results"]),
        DangerAction(
            t("players.action.delete"), h["delete"], tip=t("players.action.delete.tip")
        ),
    ]
