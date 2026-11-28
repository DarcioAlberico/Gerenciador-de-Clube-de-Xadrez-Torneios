from __future__ import annotations

# ruff: noqa: E402,I001

import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tkinter import TclError
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from PIL import Image as PILImage
from PIL import ImageGrab
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.database import Database
from src.core.services import (
    CertificateService,
    ClubService,
    CommunicationService,
    EventService,
    ExerciseService,
    FinanceService,
    GuardianService,
    InventoryService,
    LearningLevelService,
    LibraryService,
    MemberService,
    PairingService,
    RefereeService,
    TeamService,
    TournamentService,
    TrainingService,
)
from src.ui.app import AlbericusApp


DOCS_DIR = ROOT / "docs"
SCREENSHOT_DIR = DOCS_DIR / "manual_screenshots"
OUTPUT_PDF = DOCS_DIR / "Manual_Albericus.pdf"
OUTPUT_MD = DOCS_DIR / "Manual_Albericus.md"


@dataclass(frozen=True)
class MenuEntry:
    menu: str
    action: str
    shortcut: str = ""
    destination: str = ""


@dataclass(frozen=True)
class ScreenSpec:
    slug: str
    menu: str
    action: str
    title: str
    overview: str
    functions: tuple[str, ...]
    workflow: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    tabs: tuple[str, ...] = ()
    method_name: str | None = None
    tournament: str = "individual"
    capture_kind: str = "window"


MENU_ENTRIES: tuple[MenuEntry, ...] = (
    MenuEntry("Clube", "Dashboard Visual", "Ctrl+1", "Dashboard Visual"),
    MenuEntry("Clube", "Perfil do Clube", "", "Perfil do Clube"),
    MenuEntry("Clube", "Membros", "", "Membros"),
    MenuEntry("Clube", "Níveis", "", "Níveis de Aprendizagem"),
    MenuEntry("Clube", "Responsáveis", "", "Responsáveis"),
    MenuEntry("Treinamento", "Aulas", "", "Aulas e Presenças"),
    MenuEntry("Treinamento", "Exercícios", "", "Exercícios e Listas"),
    MenuEntry("Gestão", "Árbitros", "", "Árbitros"),
    MenuEntry("Gestão", "Inventário", "", "Inventário"),
    MenuEntry("Gestão", "Financeiro", "", "Financeiro"),
    MenuEntry("Gestão", "Calendário", "", "Calendário"),
    MenuEntry("Gestão", "Ranking Interno", "", "Ranking Interno"),
    MenuEntry("Torneio", "Torneios", "Ctrl+2", "Torneios"),
    MenuEntry("Torneio", "Central do Torneio", "Ctrl+3", "Central do Torneio"),
    MenuEntry("Torneio", "Painel do Árbitro", "", "Painel do Árbitro"),
    MenuEntry("Torneio", "Config. Torneio", "", "Configuração do Torneio"),
    MenuEntry("Torneio", "Jogadores", "", "Jogadores"),
    MenuEntry("Torneio", "Equipes", "", "Equipes"),
    MenuEntry("Torneio", "Rodadas", "Ctrl+4", "Rodadas e Resultados"),
    MenuEntry("Torneio", "Classificação", "Ctrl+5", "Classificação"),
    MenuEntry("Torneio", "Diplomas", "", "Diplomas"),
    MenuEntry("Ferramentas", "Exportar", "", "Exportar"),
    MenuEntry("Ferramentas", "Relatórios Administrativos", "", "Relatórios Administrativos"),
    MenuEntry("Ferramentas", "DRE Financeiro", "", "DRE Financeiro"),
    MenuEntry("Ferramentas", "Comunicação", "", "Comunicação"),
    MenuEntry("Ferramentas", "Integrações Operacionais", "", "Integrações Operacionais"),
    MenuEntry("Configurações", "Config. App", "Ctrl+,", "Configurações do Aplicativo"),
    MenuEntry("Configurações", "Auditoria Completa", "", "Auditoria Completa"),
    MenuEntry("Ajuda", "Buscar ação...", "Ctrl+K", "Palette de Comandos"),
    MenuEntry("Ajuda", "Apoie o Projeto", "", "Janela de apoio/PIX"),
    MenuEntry("Ctrl+K", "Biblioteca Pedagógica", "", "Biblioteca Pedagógica"),
    MenuEntry("Global", "Recarregar tela", "F5", "Reexecuta a tela atual"),
)


SCREENS: tuple[ScreenSpec, ...] = (
    ScreenSpec(
        slug="login",
        menu="Inicial",
        action="Acesso Restrito",
        title="Tela de Login",
        overview="Primeira tela exibida na abertura do Albericus quando o controle de acesso esta ativo.",
        functions=(
            "Informa usuário e senha do operador.",
            "Bloqueia a navegação até uma autenticação valida.",
            "Permite entrar pela tecla Enter depois de preencher a senha.",
            "Exibe aviso de campos obrigatórios ou credenciais inválidas.",
        ),
        workflow=("Digite o usuário.", "Digite a senha.", "Clique em Entrar ou pressione Enter."),
        notes=("Operadores e permissões são administrados em Configurações do Aplicativo > Segurança e dados.",),
        capture_kind="login",
    ),
    ScreenSpec(
        slug="dashboard_visual",
        menu="Clube",
        action="Dashboard Visual",
        title="Dashboard Visual",
        overview="Painel gráfico de abertura para acompanhar situação do clube, membros, caixa e agenda.",
        functions=(
            "Mostra gráfico de status dos membros.",
            "Mostra gráfico financeiro com recebido, pendente e atrasado.",
            "Exibe mural de avisos ativos.",
            "Lista próximos eventos cadastrados no calendário.",
        ),
        workflow=("Use como tela inicial de acompanhamento.", "Abra os módulos de detalhe quando algum indicador exigir ação."),
        method_name="show_visual_dashboard",
    ),
    ScreenSpec(
        slug="clube",
        menu="Clube",
        action="Perfil do Clube",
        title="Perfil do Clube, Escola ou Projeto",
        overview="Cadastro das unidades que organizam membros, turmas, aulas, torneios e relatórios.",
        functions=(
            "Cria e edita clubes, escolas, projetos e parceiros.",
            "Mantém dados de contato, endereço, cidade e observações.",
            "Cadastra turmas vinculadas a uma unidade.",
            "Carrega indicadores operacionais da unidade selecionada.",
        ),
        workflow=("Cadastre a unidade principal.", "Salve as turmas usadas em aulas e torneios.", "Selecione uma unidade para editar ou revisar dados."),
        notes=("Comece por esta tela antes de montar rotinas de clube, treinamento ou torneios integrados.",),
        method_name="show_club",
    ),
    ScreenSpec(
        slug="membros",
        menu="Clube",
        action="Membros",
        title="Membros",
        overview="Cadastro central de alunos, sócios, visitantes e convidados.",
        functions=(
            "Registra nome, sobrenome, rating, categoria, documentos, contatos e nascimento.",
            "Associa o membro a clube, turma e nível pedagógico.",
            "Filtra por texto, clube, turma, tipo, status e categoria.",
            "Mostra histórico esportivo, financeiro, presenças e variação de rating do membro selecionado.",
        ),
        workflow=("Cadastre membros ativos.", "Associe turma e nível quando aplicável.", "Use o histórico para conferir pendências ou participações."),
        notes=("Membros ativos podem ser inscritos automaticamente em torneios de clube ou turma.",),
        method_name="show_members",
    ),
    ScreenSpec(
        slug="niveis",
        menu="Clube",
        action="Níveis",
        title="Níveis de Aprendizagem",
        overview="Estrutura pedagógica usada para organizar alunos, aulas, exercícios e listas de treino.",
        functions=(
            "Cria níveis como Iniciante, Intermediário e Avançado.",
            "Define descrição e ordem de exibição.",
            "Ativa ou inativa níveis sem apagar histórico.",
            "Mostra quantos membros estão vinculados a cada nível.",
        ),
        workflow=("Crie os níveis do método de ensino.", "Aplique o nível em membros e exercícios.", "Mantenha a ordem para leitura rápida nos filtros."),
        method_name="show_learning_levels",
    ),
    ScreenSpec(
        slug="responsaveis",
        menu="Clube",
        action="Responsáveis",
        title="Responsáveis",
        overview="Controle de contatos de pais, responsáveis legais e contatos de emergência.",
        functions=(
            "Cadastra responsável com telefone, e-mail, documento, endereço e observações.",
            "Vincula responsável a um ou mais membros.",
            "Marca contato principal e contato de emergência.",
            "Lista menores sem responsável para correção cadastral.",
        ),
        workflow=("Cadastre o responsável.", "Selecione o aluno.", "Informe parentesco e marque contato principal/emergência quando necessário."),
        method_name="show_guardians",
    ),
    ScreenSpec(
        slug="aulas",
        menu="Treinamento",
        action="Aulas",
        title="Aulas e Presenças",
        overview="Agenda aulas, treinos e chamadas vinculadas ao clube, turma e lista de exercícios.",
        functions=(
            "Registra título, tipo, data, horário, instrutor, local, objetivo e conteúdo.",
            "Vincula aula a clube, turma, nível e lista de treino.",
            "Carrega chamada dos membros da turma.",
            "Salva presenças como presente, ausente ou justificada.",
        ),
        workflow=("Cadastre a aula.", "Selecione a sessão criada.", "Marque a chamada e salve.", "Use os dados em relatórios de presença."),
        notes=("Datas usam formato AAAA-MM-DD.",),
        method_name="show_training",
    ),
    ScreenSpec(
        slug="exercicios",
        menu="Treinamento",
        action="Exercícios",
        title="Exercícios e Listas",
        overview="Biblioteca tática operacional para aulas, listas de treino e acompanhamento pedagógico.",
        functions=(
            "Cadastra exercício com tema, FEN, PGN, solução, objetivo, dificuldade e tags.",
            "Filtra exercícios por busca, dificuldade e status.",
            "Cria listas de treino por clube, turma, nível e data alvo.",
            "Adiciona ou remove exercícios da lista selecionada.",
        ),
        workflow=("Cadastre exercícios reutilizáveis.", "Crie uma lista para a turma.", "Adicione exercícios selecionados.", "Vincule a lista a uma aula."),
        method_name="show_exercises",
    ),
    ScreenSpec(
        slug="arbitros",
        menu="Gestão",
        action="Árbitros",
        title="Árbitros",
        overview="Cadastro da equipe de arbitragem, usado em torneios e relatórios oficiais.",
        functions=(
            "Registra nome, categoria, ID de federação, FIDE ID, CBX ID, telefone e e-mail.",
            "Marca árbitro como ativo ou inativo.",
            "Lista todos os árbitros para seleção e edição.",
            "Permite manter observações administrativas.",
        ),
        workflow=("Cadastre os árbitros uma vez.", "Mantenha IDs oficiais atualizados.", "Associe árbitros ao torneio nas configurações do torneio quando necessário."),
        method_name="show_referees",
    ),
    ScreenSpec(
        slug="inventario",
        menu="Gestão",
        action="Inventário",
        title="Inventário",
        overview="Controle de material físico do clube: relógios, pecas, tabuleiros, livros e itens diversos.",
        functions=(
            "Cadastra item, código, tipo, quantidade, estado, local de armazenamento e valor.",
            "Registra empréstimos por membro, quantidade, data, vencimento e devolução.",
            "Registra manutenções com status, custo, fornecedor e observações.",
            "Resume itens disponíveis, emprestados, atrasados e em manutenção.",
        ),
        workflow=("Cadastre o estoque.", "Registre empréstimos quando o material sair.", "Feche devoluções e manutenções para manter saldo correto."),
        method_name="show_inventory",
    ),
    ScreenSpec(
        slug="financeiro",
        menu="Gestão",
        action="Financeiro",
        title="Financeiro",
        overview="Controle de planos, mensalidades, pagamentos, lançamentos e patrocinadores.",
        functions=(
            "Cria planos de cobrança com valor, ciclo e status.",
            "Lança pagamentos por membro, plano, referência, vencimento e método.",
            "Classifica pagamentos como pago, pendente ou atrasado.",
            "Mostra resumo de recebido, pendente, atrasado e fluxo financeiro.",
        ),
        workflow=("Crie os planos.", "Lance mensalidades ou pagamentos avulsos.", "Use filtros para cobrar pendências.", "Gere DRE em Ferramentas quando precisar consolidar."),
        method_name="show_finance",
    ),
    ScreenSpec(
        slug="calendario",
        menu="Gestão",
        action="Calendário",
        title="Calendário",
        overview="Agenda de eventos do clube, com possibilidade de vincular torneios.",
        functions=(
            "Registra título, tipo, data, horário, local, status, clube e torneio vinculado.",
            "Filtra eventos por texto, período e status.",
            "Permite acompanhar eventos planejados, confirmados, concluídos ou cancelados.",
            "Alimenta o dashboard visual e relatórios administrativos.",
        ),
        workflow=("Cadastre eventos futuros.", "Vincule torneios quando houver.", "Atualize status conforme a execução."),
        method_name="show_calendar",
    ),
    ScreenSpec(
        slug="ranking_interno",
        menu="Gestão",
        action="Ranking Interno",
        title="Ranking Interno",
        overview="Rating interno dos membros, calculado a partir dos resultados registrados.",
        functions=(
            "Mostra rating, variação, partidas, aproveitamento, resultado acumulado e última performance.",
            "Filtra por categoria, status e busca textual.",
            "Aplica resultados do torneio atual ao rating interno.",
            "Exporta a tabela de ranking.",
        ),
        workflow=("Feche rodadas do torneio.", "Revise a classificação.", "Aplique o torneio atual ao ranking interno.", "Exporte a tabela para divulgação."),
        notes=("Convidados externos não entram como membros no ranking interno.",),
        method_name="show_internal_ranking",
    ),
    ScreenSpec(
        slug="torneios",
        menu="Torneio",
        action="Torneios",
        title="Torneios",
        overview="Cria, importa, seleciona, duplica, divide e exclui torneios.",
        functions=(
            "Cria torneio individual ou por equipes.",
            "Define escopo avulso, clube/escola ou turma.",
            "Importa TRF do Swiss-Manager.",
            "Seleciona o torneio ativo para as demais telas.",
        ),
        workflow=("Preencha nome, local, datas, rodadas, ritmo e bye.", "Escolha escopo e formato.", "Crie ou importe.", "Selecione o torneio antes de usar jogadores e rodadas."),
        notes=("Sem torneio selecionado, telas como Jogadores, Rodadas, Classificação, Exportar e Diplomas ficam bloqueadas.",),
        method_name="show_tournaments",
    ),
    ScreenSpec(
        slug="central_torneio",
        menu="Torneio",
        action="Central do Torneio",
        title="Central do Torneio",
        overview="Resumo do torneio selecionado e porta de entrada para as abas de operação.",
        functions=(
            "Mostra formato, status, local, período, rodadas geradas, jogadores e perfil.",
            "Exibe navegação interna: Central, Árbitro, Config., Jogadores, Rodadas, Classificação, Exportar e Diplomas.",
            "Mostra Equipes quando o torneio esta no formato por equipes.",
            "Permite voltar para a lista de torneios.",
        ),
        workflow=("Selecione o torneio.", "Revise o resumo.", "Use a navegação da própria tela para operar o evento."),
        method_name="show_tournament_dashboard",
    ),
    ScreenSpec(
        slug="painel_arbitro",
        menu="Torneio",
        action="Painel do Árbitro",
        title="Painel do Árbitro",
        overview="Painel operacional para acompanhar pendências, rodadas, mesas, alertas e ações criticas da arbitragem.",
        functions=(
            "Mostra métricas de rodadas, resultados pendentes, jogadores ativos e pendências.",
            "Lista mesas pendentes com busca por mesa ou jogador.",
            "Oferece atalhos para Central de pendências, Ajustes de pontos, Proibições e Byes solicitados.",
            "Permite abrir lançamento de resultados e fechar rodada quando permitido.",
        ),
        workflow=("Abra durante a rodada.", "Use a busca para localizar mesa.", "Resolva pendências antes do fechamento.", "Atualize a tela periodicamente ou use auto-refresh."),
        method_name="show_arbitration_panel",
    ),
    ScreenSpec(
        slug="pendencias_arbitragem",
        menu="Painel do Árbitro",
        action="Central de Pendências",
        title="Central de Pendências da Arbitragem",
        overview="Lista alertas técnicos que podem exigir ação do árbitro antes de gerar ou fechar rodadas.",
        functions=(
            "Agrupa pendências bloqueantes, avisos, QR e conflitos.",
            "Filtra por tipo de pendência e busca textual.",
            "Mostra detalhes técnicos por duplo clique ou botão Detalhes.",
            "Permite aprovar/rejeitar QR e marcar ciência de um alerta.",
        ),
        workflow=("Filtre pelas pendências bloqueantes.", "Abra detalhes.", "Aplique correção no modulo indicado.", "Marque ciência apenas quando a ocorrência for aceitável."),
        method_name="show_arbitration_issues",
    ),
    ScreenSpec(
        slug="ajustes_pontos",
        menu="Painel do Árbitro",
        action="Ajustes de pontos (TRF25)",
        title="Ajustes de Pontos",
        overview="Registra bonificações ou penalidades manuais que devem entrar nos cálculos e exportações.",
        functions=(
            "Seleciona jogador ou equipe conforme o formato do torneio.",
            "Define rodada, tipo AAT, pontos de match, pontos de jogo e justificativa.",
            "Lista ajustes já cadastrados.",
            "Remove ajuste selecionado quando necessário.",
        ),
        workflow=("Escolha o participante.", "Informe rodada e pontos.", "Descreva a justificativa.", "Revise classificação e exportação depois do ajuste."),
        method_name="show_point_adjustments",
    ),
    ScreenSpec(
        slug="proibicoes",
        menu="Painel do Árbitro",
        action="Proibições (TRF25)",
        title="Proibições de Emparceiramento",
        overview="Impede que determinados jogadores ou equipes sejam pareados em uma janela de rodadas.",
        functions=(
            "Seleciona dois participantes.",
            "Define primeira e última rodada de validade.",
            "Registra motivo da proibição.",
            "Remove proibições quando deixarem de valer.",
        ),
        workflow=("Cadastre a proibição antes de gerar a rodada afetada.", "Use última rodada vazia/zero para manter aberta.", "Confira a pré-visualização da rodada depois."),
        method_name="show_prohibited_pairings",
    ),
    ScreenSpec(
        slug="byes_solicitados",
        menu="Painel do Árbitro",
        action="Byes solicitados (TRF25)",
        title="Byes Solicitados",
        overview="Registra pedidos de bye para que o motor de emparceiramento trate ausências autorizadas.",
        functions=(
            "Seleciona jogador, rodada e tipo de bye.",
            "Aceita tipos F, H e Z conforme configuração operacional.",
            "Mantém justificativa textual.",
            "Remove solicitações incorretas.",
        ),
        workflow=("Registre o bye antes de gerar a rodada.", "Confirme se o jogador permanece com status adequado.", "Gere a rodada e revise a mesa de bye."),
        method_name="show_requested_byes",
    ),
    ScreenSpec(
        slug="config_torneio",
        menu="Torneio",
        action="Config. Torneio",
        title="Configuração do Torneio",
        overview="Dados oficiais, agenda, regras, flags, perfis, critérios e parâmetros normativos do torneio.",
        functions=(
            "Edita dados gerais: nome, escopo, local, datas, rodadas, ritmo e bye.",
            "Mantém dados oficiais: FIDE Event-ID, organizador, página, diretores, árbitros, federação, categorias e prêmios.",
            "Configura sistema de emparceiramento, aceleração, critérios de desempate e perfil do torneio.",
            "Controla flags como inscrição publica, ocultar classificação, desativar bye e mudanças perigosas.",
        ),
        workflow=("Revise dados oficiais antes da primeira rodada.", "Defina agenda de rodadas.", "Ajuste regras e critérios.", "Evite alterar parâmetros sensíveis depois de rodadas fechadas."),
        method_name="show_tournament_settings",
    ),
    ScreenSpec(
        slug="jogadores",
        menu="Torneio",
        action="Jogadores",
        title="Jogadores",
        overview="Inscrição e manutenção dos participantes do torneio selecionado.",
        functions=(
            "Adiciona jogador manualmente com nome, rating, categoria, clube e IDs oficiais.",
            "Inscreve membros ativos do clube/turma quando o escopo permite.",
            "Importa CSV, TRF/Chess-Results e dados de formulário quando configurado.",
            "Atualiza dados oficiais por FIDE/CBX/LBX e controla status do jogador.",
        ),
        workflow=("Inscreva os participantes.", "Atualize dados oficiais.", "Revise status ativo, ausente, desistente ou não emparceirado.", "Só gere rodada quando a lista estiver correta."),
        notes=("Apenas jogadores ativos entram normalmente nas próximas rodadas.",),
        method_name="show_players",
    ),
    ScreenSpec(
        slug="equipes",
        menu="Torneio",
        action="Equipes",
        title="Equipes",
        overview="Cadastro de equipes, escalação de jogadores e tabuleiros para torneios por equipes.",
        functions=(
            "Cria equipe com nome, clube/cidade, capitão, observações e status.",
            "Seleciona jogador inscrito e atribui tabuleiro e função.",
            "Lista equipes e jogadores escalados.",
            "Bloqueia exclusão quando a equipe já apareceu em rodadas, preservando histórico.",
        ),
        workflow=("Crie o torneio no formato Equipes.", "Inscreva jogadores.", "Crie equipes.", "Associe jogadores a tabuleiros antes de gerar a rodada."),
        notes=("Em torneio individual, esta tela informa que o formato precisa ser alterado para Equipes.",),
        method_name="show_teams",
        tournament="team",
    ),
    ScreenSpec(
        slug="rodadas",
        menu="Torneio",
        action="Rodadas",
        title="Rodadas e Resultados",
        overview="Gera emparceiramentos, lança resultados, exporta listas de mesas e fecha rodadas.",
        functions=(
            "Gera próxima rodada e pré-visualiza antes de gravar.",
            "Lança resultado da mesa selecionada.",
            "Troca cores ou jogador antes do fechamento quando permitido.",
            "Exporta/imprime rodada, súmulas, cartões de mesa e QR de resultado.",
        ),
        workflow=("Gere a rodada.", "Imprima ou publique as mesas.", "Lance todos os resultados.", "Feche a rodada somente depois de conferir pendências."),
        notes=("Rodada fechada fica protegida; alterações posteriores exigem permissão/configuração especifica.",),
        method_name="show_pairings",
    ),
    ScreenSpec(
        slug="classificacao",
        menu="Torneio",
        action="Classificação",
        title="Classificação",
        overview="Tabela de pontuação e desempates do torneio selecionado.",
        functions=(
            "Recalcula a classificação a qualquer momento.",
            "Filtra por categoria.",
            "Mostra pontos, Buchholz, Buchholz mediano, Sonneborn-Berger, vitórias, performance, rating e clube.",
            "Permite abrir detalhes de desempate e atualizar ranking interno.",
        ),
        workflow=("Recalcule após salvar/fechar rodadas.", "Filtre categorias para premiação.", "Use os detalhes para explicar desempates.", "Exporte pelo modulo Exportar."),
        method_name="show_standings",
    ),
    ScreenSpec(
        slug="diplomas",
        menu="Torneio",
        action="Diplomas",
        title="Diplomas",
        overview="Gera certificados e diplomas em PDF para participantes e premiados.",
        functions=(
            "Seleciona ou cria modelo de diploma.",
            "Configura tipo, orientação, logos, fundo, cores, fontes, textos e assinaturas.",
            "Escolhe destinatários: todos, Top N geral, Top N por categoria ou selecionados.",
            "Gera PDF e registra emissões com código de verificação.",
        ),
        workflow=("Revise a classificação.", "Escolha modelo e destinatários.", "Confira a contagem/preview.", "Gere o PDF final."),
        method_name="show_certificates",
    ),
    ScreenSpec(
        slug="exportar",
        menu="Ferramentas",
        action="Exportar",
        title="Exportar",
        overview="Gera arquivos do torneio e publicações externas.",
        functions=(
            "Exporta completo, classificação, rodada especifica, todas as rodadas, jogadores e site HTML.",
            "Gera CSV, XLSX e PDF conforme o tipo escolhido.",
            "Valida TRF FIDE antes de enviar a federações ou Chess-Results.",
            "Gera lote de arquivos e pacote web quando necessário.",
        ),
        workflow=("Escolha o tipo de exportação.", "Escolha formato e rodada quando aplicável.", "Valide TRF quando for arquivo oficial.", "Salve na pasta de exportação."),
        method_name="show_export",
    ),
    ScreenSpec(
        slug="relatorios_admin",
        menu="Ferramentas",
        action="Relatórios Administrativos",
        title="Relatórios Administrativos",
        overview="Relatórios gerenciais do clube, membros, aulas, eventos, financeiro e ranking.",
        functions=(
            "Gera relatório geral do clube.",
            "Gera relatório individual de membro.",
            "Gera relatórios por período: torneios, presenças, financeiro e eventos.",
            "Gera pacote administrativo consolidado.",
        ),
        workflow=("Escolha o tipo de relatório.", "Informe período ou membro quando exigido.", "Escolha CSV, XLSX ou PDF.", "Clique em Gerar relatório."),
        method_name="show_administrative_reports",
    ),
    ScreenSpec(
        slug="dre_financeiro",
        menu="Ferramentas",
        action="DRE Financeiro",
        title="DRE Financeiro",
        overview="Demonstrativo financeiro por período, com receitas, despesas e resultado liquido.",
        functions=(
            "Calcula receitas por categoria.",
            "Calcula despesas por categoria.",
            "Mostra resultado liquido do período.",
            "Gera PDF do DRE.",
        ),
        workflow=("Informe data inicial e final.", "Clique em Calcular.", "Revise categorias.", "Gere PDF do DRE quando precisar prestar contas."),
        method_name="show_financial_reports",
    ),
    ScreenSpec(
        slug="comunicacao",
        menu="Ferramentas",
        action="Comunicação",
        title="Comunicação",
        overview="Envio de comunicados por e-mail, disparo em massa, WhatsApp e configuração SMTP.",
        functions=(
            "Envia e-mail individual por destinatário, assunto e mensagem.",
            "Faz disparo em massa para todos ativos, por turma ou por tipo de membro.",
            "Agenda e cancela mensagens pendentes.",
            "Abre mensagem no WhatsApp e salva configuração SMTP.",
        ),
        workflow=("Configure SMTP.", "Escolha e-mail individual ou disparo em massa.", "Defina publico e mensagem.", "Envie agora ou informe data/hora para agendar."),
        tabs=("E-mail", "Disparo em massa", "WhatsApp", "Config. SMTP"),
        method_name="show_communication",
    ),
    ScreenSpec(
        slug="integracoes",
        menu="Ferramentas",
        action="Integrações Operacionais",
        title="Integrações Operacionais",
        overview="Eventos de relógio/ausência e publicação de álbum por FTP.",
        functions=(
            "Registra eventos manuais de relógio/ausência e mostra os alertas.",
            "Liga ou desliga relógios conectados e notificações.",
            "Configura FTP para o álbum de fotos.",
        ),
        workflow=("Ligue os relógios conectados, se houver.", "Use eventos de relógio para auditoria operacional.", "Publique o álbum ao fim da rodada."),
        tabs=("Relógio/Ausência", "Álbum/FTP"),
        method_name="show_integrations",
    ),
    ScreenSpec(
        slug="biblioteca",
        menu="Ctrl+K",
        action="Biblioteca Pedagógica",
        title="Biblioteca Pedagógica",
        overview="Acervo pedagógico para exercícios, textos, apostilas, importação PGN e histórico de envio.",
        functions=(
            "Cadastra exercícios e textos com FEN/PGN, tema, nível, solução, tags e autor.",
            "Cria apostilas e exporta PDF do aluno ou professor.",
            "Extrai exercícios de PGN marcado com lances fortes.",
            "Registra envio manual para turmas e alerta repetições recentes.",
        ),
        workflow=("Cadastre itens no acervo.", "Monte apostilas.", "Exporte para aluno/professor.", "Registre envios para controlar repetição."),
        tabs=("Acervo", "Apostilas", "Importador PGN", "Histórico de Envio"),
        method_name="show_library",
    ),
    ScreenSpec(
        slug="config_app",
        menu="Configurações",
        action="Config. App",
        title="Configurações do Aplicativo",
        overview="Preferências locais, pastas, backup, segurança, usuários e bases oficiais.",
        functions=(
            "Ajusta aparência, cor de destaque e escala da interface.",
            "Define pastas de exportação, backups e nuvem.",
            "Gerencia usuários do sistema e permissões por perfil.",
            "Baixa lista FIDE, importa lista CBX e cria/restaura backups.",
        ),
        workflow=("Configure pastas antes de operar torneios.", "Crie backup antes de mudanças importantes.", "Revise retenção.", "Use restauração apenas com backup conferido."),
        tabs=("Aparência", "Pastas e backup", "Segurança e dados"),
        method_name="show_app_settings",
    ),
    ScreenSpec(
        slug="auditoria",
        menu="Configurações",
        action="Auditoria Completa",
        title="Auditoria Completa",
        overview="Consulta de logs técnicos e administrativos do sistema.",
        functions=(
            "Filtra por data inicial, data final, operador, ação e entidade.",
            "Lista data, operador, perfil, ação, entidade e descrição.",
            "Abre metadados JSON por duplo clique.",
            "Ajuda a investigar backups, restaurações, logins, permissões e operações sensíveis.",
        ),
        workflow=("Defina filtros.", "Clique em Buscar.", "Abra metadados quando precisar de detalhe técnico.", "Use como trilha de auditoria e suporte."),
        method_name="show_audit_logs",
    ),
    ScreenSpec(
        slug="palette",
        menu="Ajuda",
        action="Buscar ação...",
        title="Palette de Comandos",
        overview="Busca rápida de telas e comandos por teclado.",
        functions=(
            "Abre com Ctrl+K.",
            "Filtra ações por nome e palavras-chave.",
            "Executa a ação selecionada com Enter.",
            "Inclui atalhos que não aparecem no menu principal, como Biblioteca Pedagógica.",
        ),
        workflow=("Pressione Ctrl+K.", "Digite parte do nome da tela.", "Use setas para escolher.", "Pressione Enter."),
        method_name="_show_command_palette",
        capture_kind="palette",
    ),
)


def main() -> None:
    DOCS_DIR.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temp_name:
        temp_dir = Path(temp_name)
        db = Database(temp_dir / "albericus_manual_demo.db", backup_dir=temp_dir / "backups")
        demo_ids = seed_demo_database(db, temp_dir)
        screenshots = capture_screenshots(db, demo_ids)

    build_markdown(screenshots)
    build_pdf(screenshots)
    print(OUTPUT_MD.resolve())
    print(OUTPUT_PDF.resolve())


def seed_demo_database(db: Database, temp_dir: Path) -> dict[str, int]:
    club_service = ClubService(db)
    member_service = MemberService(db)
    guardian_service = GuardianService(db)
    level_service = LearningLevelService(db)
    training_service = TrainingService(db)
    exercise_service = ExerciseService(db)
    finance_service = FinanceService(db)
    event_service = EventService(db)
    communication_service = CommunicationService(db)
    inventory_service = InventoryService(db)
    tournament_service = TournamentService(db)
    pairing_service = PairingService(db)
    referee_service = RefereeService(db)
    team_service = TeamService(db)
    library_service = LibraryService(db)
    certificate_service = CertificateService(db, pairing_service)

    db.save_app_settings(
        {
            "operator_name": "Admin Manual",
            "operator_role": "admin",
            "default_export_dir": str(temp_dir / "exports"),
            "backup_dir": str(temp_dir / "backups"),
            "backup_retention_count": "10",
            "ui_scale_percent": "100",
        }
    )

    club_id = club_service.save_profile(
        {
            "name": "Clube Modelo Albericus",
            "kind": "club",
            "city": "São Paulo",
            "address": "Rua das Torres, 64",
            "phone": "(11) 99999-0000",
            "email": "contato@clubemodelo.com",
            "notes": "Unidade usada no manual.",
            "active": 1,
        },
        club_id=1,
    )
    class_id = club_service.save_class(
        {
            "club_id": club_id,
            "name": "Turma Sub-18",
            "teacher": "Prof. Marcos",
            "weekday": "Sábado",
            "time": "09:00",
            "location": "Sala 2",
            "active": 1,
            "notes": "Treino semanal.",
        }
    )

    def ensure_level(name: str, description: str, display_order: int) -> int:
        existing = next(
            (item for item in db.list_learning_levels(active_only=False) if str(item["name"]).casefold() == name.casefold()),
            None,
        )
        if existing:
            return int(existing["id"])
        return level_service.create_level(
            {"name": name, "description": description, "display_order": display_order}
        )

    level_ids = [
        ensure_level("Iniciante", "Fundamentos e mates básicos.", 1),
        ensure_level("Intermediário", "Tática, finais e estratégia.", 2),
        ensure_level("Avançado", "Preparação competitiva.", 3),
    ]

    members = [
        ("Ana", "Silva", 1680, "Sub-18", "2010-03-12", level_ids[1]),
        ("Bruno", "Costa", 1740, "Absoluto", "1997-08-20", level_ids[2]),
        ("Carla", "Lima", 1605, "Feminino", "2008-11-05", level_ids[1]),
        ("Diego", "Rocha", 1510, "Sub-18", "2009-07-18", level_ids[0]),
        ("Elisa", "Mendes", 1820, "Absoluto", "1993-02-02", level_ids[2]),
        ("Gustavo", "Nunes", 1490, "Sub-18", "2011-04-14", level_ids[0]),
    ]
    member_ids: list[int] = []
    for index, (name, surname, rating, category, birth_date, level_id) in enumerate(members, start=1):
        member_ids.append(
            member_service.create_member(
                {
                    "name": name,
                    "surname": surname,
                    "club_id": club_id,
                    "class_id": class_id,
                    "learning_level_id": level_id,
                    "member_type": "aluno" if category != "Absoluto" else "socio",
                    "status": "active",
                    "rating": str(rating),
                    "category": category,
                    "phone": f"(11) 90000-000{index}",
                    "email": f"{name.lower()}@example.com",
                    "birth_date": birth_date,
                    "document": "",
                    "guardian_name": "",
                    "guardian_phone": "",
                    "notes": "Cadastro de demonstração.",
                }
            )
        )

    guardian_id = guardian_service.create_guardian(
        {
            "name": "Maria Silva",
            "phone": "(11) 98888-1111",
            "email": "maria@example.com",
            "document": "000.000.000-00",
            "address": "Rua das Torres, 64",
            "notes": "Responsável pela Ana.",
            "active": 1,
        }
    )
    guardian_service.link_guardian_to_member(
        {
            "guardian_id": guardian_id,
            "member_id": member_ids[0],
            "relationship": "Mãe",
            "primary_contact": 1,
            "emergency_contact": 1,
            "notes": "Contato principal.",
        }
    )

    exercise_id = exercise_service.save_exercise(
        {
            "club_id": club_id,
            "learning_level_id": level_ids[1],
            "title": "Mate em duas - coluna aberta",
            "theme": "Tática",
            "difficulty": "basic",
            "source": "Apostila interna",
            "fen": "6k1/5ppp/8/8/8/8/5PPP/6K1 w - - 0 1",
            "pgn": "",
            "solution": "Ativar a torre e explorar a retaguarda.",
            "objective": "Reconhecer padrões de mate.",
            "tags": "mate, torre, iniciante",
            "active": 1,
            "notes": "Exemplo do manual.",
        }
    )
    list_id = exercise_service.save_training_list(
        {
            "club_id": club_id,
            "class_id": class_id,
            "learning_level_id": level_ids[1],
            "name": "Lista de Táticas - Maio",
            "description": "Exercícios curtos para treino de cálculo.",
            "target_date": "2026-05-16",
            "status": "ready",
        }
    )
    exercise_service.add_exercise_to_training_list(list_id, exercise_id)
    exercise_service.record_attempt(
        {
            "exercise_id": exercise_id,
            "member_id": member_ids[0],
            "list_id": list_id,
            "attempt_date": "2026-05-16",
            "result": "correct",
            "score": "1",
            "time_seconds": "95",
            "notes": "Resolvido em sala.",
        }
    )

    session_id = training_service.save_session(
        {
            "club_id": club_id,
            "class_id": class_id,
            "training_list_id": list_id,
            "learning_level_id": level_ids[1],
            "title": "Treino de finais",
            "session_type": "aula",
            "session_date": "2026-05-16",
            "start_time": "09:00",
            "end_time": "11:00",
            "instructor": "Prof. Marcos",
            "location": "Sala 2",
            "objective": "Finais de torre.",
            "content": "Técnicas básicas e exemplos práticos.",
            "status": "planned",
            "notes": "Aula de demonstração.",
        }
    )
    training_service.record_attendance(
        session_id,
        [
            {"member_id": member_ids[0], "status": "present", "notes": ""},
            {"member_id": member_ids[1], "status": "present", "notes": ""},
            {"member_id": member_ids[2], "status": "justified", "notes": "Viagem"},
            {"member_id": member_ids[3], "status": "absent", "notes": ""},
        ],
    )

    plan_id = finance_service.save_plan(
        {"name": "Mensalidade aluno", "amount": "120", "billing_cycle": "monthly", "active": 1, "notes": "Plano padrão."}
    )
    finance_service.save_payment(
        {
            "member_id": member_ids[0],
            "plan_id": plan_id,
            "description": "Mensalidade maio",
            "reference_period": "2026-05",
            "due_date": "2026-05-10",
            "payment_date": "2026-05-08",
            "amount": "120",
            "status": "paid",
            "method": "Pix",
            "notes": "",
        }
    )
    finance_service.save_payment(
        {
            "member_id": member_ids[1],
            "plan_id": plan_id,
            "description": "Mensalidade maio",
            "reference_period": "2026-05",
            "due_date": "2026-05-20",
            "amount": "120",
            "status": "pending",
            "method": "",
            "notes": "",
        }
    )
    finance_service.save_transaction(
        {
            "transaction_date": "2026-05-18",
            "transaction_type": "income",
            "category": "Inscrições",
            "description": "Inscrições do Aberto Primavera",
            "amount": "420",
            "payment_method": "Pix",
            "notes": "",
        }
    )
    finance_service.save_transaction(
        {
            "transaction_date": "2026-05-18",
            "transaction_type": "expense",
            "category": "Premiação",
            "description": "Medalhas e troféus",
            "amount": "180",
            "payment_method": "Cartão",
            "notes": "",
        }
    )

    item_id = inventory_service.save_item(
        {
            "club_id": club_id,
            "code": "REL-001",
            "name": "Relógio digital DGT",
            "item_type": "clocks",
            "quantity_total": "8",
            "condition_status": "good",
            "storage_location": "Armário 1",
            "acquisition_date": "2026-04-20",
            "acquisition_value": "350",
            "active": 1,
            "notes": "Usado em torneios rápidos.",
        }
    )
    inventory_service.save_loan(
        {
            "item_id": item_id,
            "member_id": member_ids[3],
            "quantity": "1",
            "loan_date": "2026-05-12",
            "due_date": "2026-05-20",
            "status": "open",
            "notes": "Empréstimo para treino.",
        }
    )
    inventory_service.save_maintenance(
        {
            "item_id": item_id,
            "opened_date": "2026-05-15",
            "status": "in_progress",
            "description": "Botão de início frouxo.",
            "cost": "35",
            "vendor": "Assistência local",
            "notes": "",
        }
    )

    individual_tournament_id = tournament_service.create_tournament(
        {
            "name": "Aberto Primavera",
            "scope": "club",
            "competition_type": "individual",
            "club_id": club_id,
            "location": "Clube Modelo",
            "start_date": "2026-05-18",
            "end_date": "2026-05-19",
            "rounds_count": "5",
            "time_control": "15+10",
            "bye_points": "1",
        }
    )
    tournament_service.save_profile(
        individual_tournament_id,
        {
            "name": "Aberto Primavera",
            "scope": "club",
            "competition_type": "individual",
            "club_id": club_id,
            "location": "Clube Modelo",
            "start_date": "2026-05-18",
            "end_date": "2026-05-19",
            "rounds_count": "5",
            "time_control": "15+10",
            "bye_points": "1",
        },
        {
            "fide_event_id": "DEMO-2026",
            "organizer": "Clube Modelo Albericus",
            "website": "https://exemplo.local",
            "contact_email": "arbitragem@example.com",
            "director": "Diretoria do clube",
            "chief_arbiter": "Árbitro Principal",
            "arbiters": "Equipe de apoio",
            "federation": "BRA",
            "state": "SP",
            "categories": "Absoluto, Sub-18, Feminino",
            "cutoff_date": "2026-05-18",
            "comments": "Torneio de demonstração do manual.",
            "prizes": "Medalhas por categoria.",
            "initial_order": "rating",
            "tournament_type": "test",
            "tournament_profile": "free",
            "late_entry_points": "0",
            "allow_public_registration": 0,
            "allow_player_result_edit": 0,
            "allow_dangerous_changes": 0,
            "disable_bye": 0,
            "accelerated_system": 0,
            "hide_standings": 0,
            "calculate_performance": 1,
            "hide_color_names": 0,
            "show_opponents_in_standings": 1,
            "archived": 0,
        },
        [
            {"round_number": 1, "date": "2026-05-18", "time": "09:00"},
            {"round_number": 2, "date": "2026-05-18", "time": "11:00"},
            {"round_number": 3, "date": "2026-05-18", "time": "14:00"},
            {"round_number": 4, "date": "2026-05-19", "time": "09:00"},
            {"round_number": 5, "date": "2026-05-19", "time": "11:00"},
        ],
    )
    member_service.register_active_members_in_tournament(individual_tournament_id)
    db.create_player(
        individual_tournament_id,
        name="Felipe Andrade",
        surname="Andrade",
        given_name="Felipe",
        rating=1660,
        club="Convidado",
        category="Absoluto",
        fide_id="123456",
        cbx_id="654321",
    )

    referee_id = referee_service.create_referee(
        {
            "name": "Árbitro Principal",
            "category": "AN",
            "federation_id": "SP-001",
            "fide_id": "3456789",
            "cbx_id": "998877",
            "phone": "(11) 97777-0000",
            "email": "arbitro@example.com",
            "notes": "Árbitro chefe do torneio demo.",
            "active": 1,
        }
    )
    referee_service.assign_tournament_referee(individual_tournament_id, referee_id, "chief")

    first_round = pairing_service.generate_next_round(individual_tournament_id)
    results = ["1-0", "0-1", "1/2-1/2"]
    for index, pairing in enumerate(db.get_pairings_for_round(first_round["id"])):
        if pairing["is_bye"]:
            continue
        pairing_service.update_result(individual_tournament_id, pairing["id"], results[index % len(results)])
    pairing_service.close_round(individual_tournament_id, first_round["id"])
    pairing_service.generate_next_round(individual_tournament_id)

    players = db.list_players(individual_tournament_id, active_only=False)
    if len(players) >= 2:
        db.add_point_adjustment(
            individual_tournament_id,
            round_number=1,
            player_id=int(players[0]["id"]),
            aat_type="manual",
            match_points=0.5,
            reason="Exemplo de ajuste homologado.",
        )
        db.add_prohibited_pairing(
            individual_tournament_id,
            int(players[0]["id"]),
            int(players[1]["id"]),
            first_round=3,
            last_round=5,
            reason="Mesmo clube/critério pedagógico.",
        )
        db.add_requested_bye(individual_tournament_id, int(players[-1]["id"]), 3, "H", reason="Compromisso escolar.")


    event_service.save_event(
        {
            "club_id": club_id,
            "tournament_id": individual_tournament_id,
            "title": "Aberto Primavera - rodada 2",
            "event_type": "tournament",
            "event_date": "2026-05-18",
            "start_time": "11:00",
            "end_time": "13:00",
            "location": "Salão principal",
            "status": "confirmed",
            "notes": "Evento vinculado ao torneio.",
        }
    )
    communication_service.save_announcement(
        {
            "club_id": club_id,
            "title": "Inscrições abertas",
            "content": "Inscrições do Aberto Primavera seguem abertas até sexta-feira.",
            "category": "torneio",
            "start_date": "2026-05-10",
            "end_date": "2026-05-18",
            "active": 1,
        }
    )

    library_item_id = library_service.save_item(
        {
            "title": "Tema tático: pino absoluto",
            "item_type": "exercise",
            "phase": "middlegame",
            "level": "intermediate",
            "fen_pgn": "6k1/5ppp/8/8/8/8/5PPP/6K1 w - - 0 1",
            "theme": "Pino",
            "solution": "Criar pressão na coluna aberta.",
            "tags": "pino,tática",
            "author": "Acervo Albericus",
            "cover_image": "",
        }
    )
    library_service.save_collection(
        {"name": "Apostila Maio", "description": "Táticas intermediarias", "items": [library_item_id]}
    )

    template_count = len(certificate_service.list_templates(active_only=True))
    if template_count == 0:
        certificate_service.create_template(
            {
                "name": "Participação padrão",
                "certificate_type": "participation",
                "orientation": "landscape",
                "title_template": "Certificado de Participação",
                "body_template": "{player_name} participou do {tournament_name}.",
                "footer_template": "Albericus",
                "signature_left": "Organização",
                "signature_right": "Arbitragem",
                "primary_color": "#1E3A8A",
                "accent_color": "#93C5FD",
                "title_font_size": 32,
                "body_font_size": 18,
                "footer_font_size": 10,
                "active": 1,
            }
        )

    team_tournament_id = tournament_service.create_tournament(
        {
            "name": "Interclubes Modelo",
            "scope": "club",
            "competition_type": "team",
            "club_id": club_id,
            "location": "Clube Modelo",
            "start_date": "2026-06-01",
            "end_date": "2026-06-02",
            "rounds_count": "3",
            "time_control": "30+30",
            "bye_points": "1",
        }
    )
    team_player_ids = [
        db.create_player(team_tournament_id, name=f"Jogador {i}", rating=1800 - i * 25, club="Equipe Azul", category="Absoluto")
        for i in range(1, 9)
    ]
    team_a = team_service.create_team(team_tournament_id, {"name": "Equipe Azul", "club": "São Paulo", "captain": "Bruno", "active": 1, "notes": ""})
    team_b = team_service.create_team(team_tournament_id, {"name": "Equipe Vermelha", "club": "Santos", "captain": "Elisa", "active": 1, "notes": ""})
    for board, player_id in enumerate(team_player_ids[:4], start=1):
        team_service.add_player(team_a, player_id, board_number=board, role="starter")
    for board, player_id in enumerate(team_player_ids[4:], start=1):
        team_service.add_player(team_b, player_id, board_number=board, role="starter")

    db.create_audit_log(
        action="manual_demo_seed",
        actor="Admin Manual",
        role="admin",
        entity_type="manual",
        description="Base de demonstração criada para o manual.",
        metadata_json='{"source":"scripts/generate_user_manual.py"}',
    )

    return {
        "individual_tournament_id": individual_tournament_id,
        "team_tournament_id": team_tournament_id,
        "club_id": club_id,
    }


def capture_screenshots(db: Database, demo_ids: dict[str, int]) -> dict[str, Path]:
    reset_screenshot_dir()
    screenshots: dict[str, Path] = {}
    app: AlbericusApp | None = None
    try:
        app = AlbericusApp(db=db)
        app.geometry("1360x820+40+10")
        app.update_idletasks()
        app.update()
        app.lift()
        app.attributes("-topmost", True)
        app.update()
        app.attributes("-topmost", False)
        time.sleep(0.25)
        screenshots["login"] = capture_widget(app, "login")

        if hasattr(app, "login_frame"):
            app.login_frame.destroy()
        app._build_menu()
        app._build_statusbar()
        app._build_content()
        app._register_shortcuts()
        app._show_info = lambda _message: None
        app._show_warning = lambda _message: None
        app._confirm_action = lambda *_args, **_kwargs: False
        app._show_error = lambda error: (_ for _ in ()).throw(error if isinstance(error, Exception) else Exception(str(error)))
        set_tournament(app, demo_ids, "individual")
        app.update_idletasks()
        app.update()

        for screen in SCREENS:
            if screen.capture_kind == "login":
                continue
            try:
                if screen.capture_kind == "palette":
                    set_tournament(app, demo_ids, "individual")
                    app._show_command_palette()
                    app.update_idletasks()
                    app.update()
                    time.sleep(0.2)
                    palette = find_toplevel(app)
                    if palette is not None:
                        palette.lift()
                        palette.attributes("-topmost", True)
                        app.update_idletasks()
                        app.update()
                        time.sleep(0.35)
                        palette.attributes("-topmost", False)
                        app.update()
                        screenshots[screen.slug] = capture_widget(palette, screen.slug)
                        palette.destroy()
                    continue

                set_tournament(app, demo_ids, screen.tournament)
                if screen.method_name:
                    getattr(app, screen.method_name)()
                app.update_idletasks()
                app.update()
                time.sleep(0.2)
                screenshots[screen.slug] = capture_widget(app, screen.slug)
            except Exception as exc:
                print(f"Captura ignorada para {screen.slug}: {exc}")
    except (TclError, OSError) as exc:
        print(f"Captura de telas ignorada: ambiente gráfico indisponível ({exc})")
    finally:
        if app is not None:
            try:
                app.destroy()
            except Exception:
                pass
    return screenshots


def set_tournament(app: AlbericusApp, demo_ids: dict[str, int], key: str) -> None:
    tournament_id = demo_ids["team_tournament_id"] if key == "team" else demo_ids["individual_tournament_id"]
    if app.current_tournament_id != tournament_id:
        app._set_current_tournament(tournament_id)


def reset_screenshot_dir() -> None:
    if SCREENSHOT_DIR.exists():
        shutil.rmtree(SCREENSHOT_DIR)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def find_toplevel(app: AlbericusApp) -> Any | None:
    for child in app.winfo_children():
        if child.__class__.__name__ == "CTkToplevel":
            return child
    return None


def capture_widget(widget: Any, slug: str) -> Path:
    widget.update_idletasks()
    left = widget.winfo_rootx()
    top = widget.winfo_rooty()
    width = widget.winfo_width()
    height = widget.winfo_height()
    if width <= 1:
        width = widget.winfo_reqwidth()
    if height <= 1:
        height = widget.winfo_reqheight()
    image = ImageGrab.grab(bbox=(left, top, left + width, top + height))
    image = image.convert("RGB")
    path = SCREENSHOT_DIR / f"{slug}.jpg"
    image.save(path, quality=86, optimize=True)
    return path


def build_markdown(screenshots: dict[str, Path]) -> None:
    today = date.today().strftime("%d/%m/%Y")
    lines: list[str] = [
        "# Manual Completo do Albericus",
        "",
        f"Gerado em {today}.",
        "",
        "Este manual documenta os menus, telas, funções principais, fluxos recomendados e cuidados operacionais do Albericus.",
        "",
        "## Sumario",
        "",
        "- [Fluxo recomendado](#fluxo-recomendado)",
        "- [Mapa dos menus](#mapa-dos-menus)",
        "- [Telas e funções](#telas-e-funções)",
        "- [Regras importantes](#regras-importantes)",
        "- [Problemas comuns](#problemas-comuns)",
        "",
        "## Fluxo recomendado",
        "",
        "1. Cadastre o clube, escola ou projeto em **Clube > Perfil do Clube**.",
        "2. Cadastre turmas, níveis, membros e responsáveis.",
        "3. Configure pastas e backups em **Configurações > Config. App**.",
        "4. Crie ou importe um torneio em **Torneio > Torneios**.",
        "5. Revise **Config. Torneio** antes da primeira rodada.",
        "6. Inscreva jogadores e atualize dados oficiais.",
        "7. Gere rodadas, lance resultados, acompanhe o **Painel do Árbitro** e feche cada rodada.",
        "8. Confira a classificação, exporte arquivos e gere diplomas/relatórios.",
        "",
        "## Mapa dos menus",
        "",
        "| Menu | Ação | Atalho | Abre/Executa |",
        "|---|---|---|---|",
    ]
    for item in MENU_ENTRIES:
        lines.append(f"| {item.menu} | {item.action} | {item.shortcut or '-'} | {item.destination} |")

    lines.extend(["", "## Telas e funções", ""])
    for screen in SCREENS:
        lines.append(f"### {screen.title}")
        lines.append("")
        lines.append(f"**Caminho:** {screen.menu} > {screen.action}")
        lines.append("")
        lines.append(screen.overview)
        lines.append("")
        path = screenshots.get(screen.slug)
        if path and path.exists():
            relative = path.relative_to(DOCS_DIR).as_posix()
            lines.append(f"![{screen.title}]({relative})")
            lines.append("")
        if screen.tabs:
            lines.append("**Abas ou áreas internas:**")
            lines.extend(f"- {item}" for item in screen.tabs)
            lines.append("")
        lines.append("**Principais funções:**")
        lines.extend(f"- {item}" for item in screen.functions)
        lines.append("")
        if screen.workflow:
            lines.append("**Fluxo recomendado:**")
            lines.extend(f"{index}. {item}" for index, item in enumerate(screen.workflow, start=1))
            lines.append("")
        if screen.notes:
            lines.append("**Cuidados:**")
            lines.extend(f"- {item}" for item in screen.notes)
            lines.append("")

    lines.extend(
        [
            "## Regras importantes",
            "",
            "- Fechar rodada exige resultados completos em todas as mesas validas.",
            "- Rodada fechada preserva histórico; alterações posteriores exigem permissão e configuração adequada.",
            "- Jogador ausente, desistente ou não emparceirado permanece no histórico, mas não deve entrar normalmente em novas rodadas.",
            "- Antes de exportar TRF ou relatório oficial, revise IDs, federação, nascimento, rating, árbitro chefe, ritmo e datas.",
            "- Backups devem ser feitos antes de fechar rodadas criticas, restaurar dados ou importar listas grandes.",
            "- Para torneios por equipes, cadastre equipes e escalações antes de gerar rodadas.",
            "",
            "## Problemas comuns",
            "",
            "| Situação | O que verificar |",
            "|---|---|",
            "| Não consigo gerar rodada | Verifique se há jogadores ativos suficientes e se a rodada anterior foi fechada ou excluída. |",
            "| A tela de torneio parece vazia | Selecione um torneio em **Torneio > Torneios**. |",
            "| Classificação não atualiza | Recalcule a classificação e confira se resultados foram salvos. |",
            "| Exportação falha | Verifique permissão da pasta e se o arquivo destino não esta aberto em outro programa. |",
            "| Login ou permissão bloqueia uma ação | Revise usuários/perfis em **Configurações > Config. App**. |",
            "| Preciso voltar dados | Use **Criar backup agora** antes e restaure apenas backups conferidos. |",
            "",
        ]
    )
    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")


def build_pdf(screenshots: dict[str, Path]) -> None:
    styles = create_styles()
    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=A4,
        rightMargin=1.4 * cm,
        leftMargin=1.4 * cm,
        topMargin=1.3 * cm,
        bottomMargin=1.3 * cm,
        title="Manual completo do Albericus",
        author="Albericus",
    )
    story: list[Any] = []
    today = date.today().strftime("%d/%m/%Y")

    story.append(Paragraph("Manual completo do Albericus", styles["CoverTitle"]))
    story.append(Paragraph("Menus, telas, funções, fluxos e screenshots", styles["CoverSubtitle"]))
    story.append(Spacer(1, 0.35 * cm))
    story.append(Paragraph(f"Gerado em {today}", styles["MutedCenter"]))
    story.append(Spacer(1, 0.8 * cm))
    story.append(
        Paragraph(
            safe(
                "Este manual documenta a interface atual do Albericus com uma base de demonstração. "
                "Use como referência operacional para clube, treinamento, torneios, arbitragem, relatórios e configurações."
            ),
            styles["Body"],
        )
    )
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("Fluxo recomendado", styles["Heading1"]))
    story.append(
        number_list(
            [
                "Cadastre clube, turmas, níveis, membros e responsáveis.",
                "Configure pastas, backups e usuários.",
                "Crie ou importe o torneio e selecione-o.",
                "Revise configurações oficiais e regras.",
                "Inscreva jogadores, gere rodadas, lance resultados e feche rodadas.",
                "Confira classificação, exporte arquivos, gere relatórios e diplomas.",
            ],
            styles,
        )
    )
    story.append(PageBreak())

    story.append(Paragraph("Mapa dos menus", styles["Heading1"]))
    menu_data = [["Menu", "Ação", "Atalho", "Abre/Executa"]]
    menu_data.extend([[item.menu, item.action, item.shortcut or "-", item.destination] for item in MENU_ENTRIES])
    menu_table = Table(menu_data, colWidths=[3.0 * cm, 5.0 * cm, 2.3 * cm, 6.3 * cm], repeatRows=1)
    menu_table.setStyle(common_table_style())
    story.append(menu_table)
    story.append(PageBreak())

    for screen in SCREENS:
        story.append(Paragraph(safe(screen.title), styles["Heading1"]))
        story.append(Paragraph(safe(f"Caminho: {screen.menu} > {screen.action}"), styles["Small"]))
        story.append(Paragraph(safe(screen.overview), styles["Body"]))
        if screen.tabs:
            story.append(Paragraph("Abas ou áreas internas", styles["Heading2"]))
            story.append(bullet_list(list(screen.tabs), styles))
        story.append(Paragraph("Principais funções", styles["Heading2"]))
        story.append(bullet_list(list(screen.functions), styles))
        if screen.workflow:
            story.append(Paragraph("Fluxo recomendado", styles["Heading2"]))
            story.append(number_list(list(screen.workflow), styles))
        if screen.notes:
            story.append(Paragraph("Cuidados", styles["Heading2"]))
            story.append(bullet_list(list(screen.notes), styles))
        story.append(screenshot_block(screen.slug, f"Screenshot: {screen.title}.", screenshots, styles))
        story.append(PageBreak())

    story.append(Paragraph("Regras importantes", styles["Heading1"]))
    story.append(
        bullet_list(
            [
                "Fechar rodada exige resultados completos em todas as mesas validas.",
                "Rodada fechada preserva histórico; alterações posteriores exigem permissão e configuração adequada.",
                "Jogadores ausentes, desistentes ou não emparceirados continuam no histórico, mas não devem entrar normalmente em novas rodadas.",
                "Revise IDs oficiais, federação, nascimento, rating, árbitro, ritmo e datas antes de exportações oficiais.",
                "Crie backups antes de fechar rodadas criticas, restaurar dados ou importar bases grandes.",
                "Em torneios por equipes, cadastre equipes e escalações antes de gerar rodadas.",
            ],
            styles,
        )
    )
    story.append(Paragraph("Problemas comuns", styles["Heading1"]))
    problem_data = [
        ["Situação", "O que verificar"],
        ["Não consigo gerar rodada", "Jogadores ativos suficientes e rodada anterior fechada ou excluída."],
        ["Tela de torneio vazia", "Selecione um torneio em Torneio > Torneios."],
        ["Classificação não atualiza", "Recalcule e confira resultados salvos."],
        ["Exportação falha", "Permissão da pasta e arquivo destino aberto em outro programa."],
        ["Ação bloqueada por permissão", "Usuários e perfis em Configurações > Config. App."],
        ["Preciso voltar dados", "Restaurar apenas backup conferido, criando copia de segurança antes."],
    ]
    problem_table = Table(problem_data, colWidths=[5.0 * cm, 11.3 * cm], repeatRows=1)
    problem_table.setStyle(common_table_style())
    story.append(problem_table)

    doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)


def safe(text: str) -> str:
    return xml_escape(str(text))


def create_styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "CoverTitle": ParagraphStyle(
            "CoverTitle",
            parent=sample["Title"],
            fontName="Helvetica-Bold",
            fontSize=27,
            leading=33,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#0F172A"),
            spaceAfter=12,
        ),
        "CoverSubtitle": ParagraphStyle(
            "CoverSubtitle",
            parent=sample["Normal"],
            fontSize=13,
            leading=18,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#475569"),
        ),
        "MutedCenter": ParagraphStyle(
            "MutedCenter",
            parent=sample["Normal"],
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#64748B"),
        ),
        "Heading1": ParagraphStyle(
            "Heading1",
            parent=sample["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=22,
            textColor=colors.HexColor("#0F172A"),
            spaceBefore=6,
            spaceAfter=7,
        ),
        "Heading2": ParagraphStyle(
            "Heading2",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12.5,
            leading=16,
            textColor=colors.HexColor("#1E293B"),
            spaceBefore=5,
            spaceAfter=4,
        ),
        "Body": ParagraphStyle(
            "Body",
            parent=sample["BodyText"],
            fontSize=9.4,
            leading=12.7,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=5,
        ),
        "Small": ParagraphStyle(
            "Small",
            parent=sample["BodyText"],
            fontSize=8.2,
            leading=11,
            textColor=colors.HexColor("#475569"),
            spaceAfter=4,
        ),
    }


def bullet_list(items: list[str], styles: dict[str, ParagraphStyle]) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(safe(item), styles["Body"]), leftIndent=8) for item in items],
        bulletType="bullet",
        leftIndent=14,
        bulletFontName="Helvetica",
        bulletFontSize=8,
        bulletColor=colors.HexColor("#2563EB"),
        spaceAfter=6,
    )


def number_list(items: list[str], styles: dict[str, ParagraphStyle]) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(safe(item), styles["Body"]), leftIndent=8) for item in items],
        bulletType="1",
        leftIndent=18,
        bulletFontName="Helvetica",
        bulletFontSize=8,
        bulletColor=colors.HexColor("#2563EB"),
        spaceAfter=6,
    )


def screenshot_block(
    slug: str,
    caption: str,
    screenshots: dict[str, Path],
    styles: dict[str, ParagraphStyle],
) -> Any:
    path = screenshots.get(slug)
    if not path or not path.exists():
        return Paragraph("Screenshot não disponível nesta geração.", styles["Small"])
    max_width = 17.0 * cm
    max_height = 10.2 * cm
    with PILImage.open(path) as image:
        width, height = image.size
    ratio = min(max_width / width, max_height / height)
    flowable = Image(str(path), width=width * ratio, height=height * ratio)
    return KeepTogether(
        [
            Spacer(1, 0.15 * cm),
            flowable,
            Paragraph(safe(caption), styles["Small"]),
        ]
    )


def common_table_style() -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
    )


def draw_footer(canvas: Any, doc: Any) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawString(1.4 * cm, 0.7 * cm, "Albericus - Manual completo")
    canvas.drawRightString(A4[0] - 1.4 * cm, 0.7 * cm, f"Página {doc.page}")
    canvas.restoreState()


if __name__ == "__main__":
    main()
