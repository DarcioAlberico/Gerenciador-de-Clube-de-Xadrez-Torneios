from __future__ import annotations

# ruff: noqa: E402,I001

import shutil
import sys
import tempfile
import time
from datetime import date
from pathlib import Path
from tkinter import TclError

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
    ClubService,
    EventService,
    FinanceService,
    GuardianService,
    MemberService,
    PairingService,
    TournamentService,
    TrainingService,
)
from src.ui import AlbericusApp


DOCS_DIR = ROOT / "docs"
SCREENSHOT_DIR = DOCS_DIR / "manual_screenshots"
OUTPUT_PDF = DOCS_DIR / "Manual_Albericus.pdf"


def main() -> None:
    DOCS_DIR.mkdir(exist_ok=True)
    screenshots: dict[str, Path] = {}

    with tempfile.TemporaryDirectory() as temp_name:
        temp_dir = Path(temp_name)
        db = Database(temp_dir / "albericus_manual_demo.db", backup_dir=temp_dir / "backups")
        tournament_id = seed_demo_database(db)
        screenshots = capture_screenshots(db, tournament_id)

    build_pdf(screenshots)
    print(OUTPUT_PDF.resolve())


def seed_demo_database(db: Database) -> int:
    club_service = ClubService(db)
    member_service = MemberService(db)
    guardian_service = GuardianService(db)
    training_service = TrainingService(db)
    finance_service = FinanceService(db)
    event_service = EventService(db)
    tournament_service = TournamentService(db)
    pairing_service = PairingService(db)

    club_id = club_service.save_profile(
        {
            "name": "Clube Modelo Albericus",
            "kind": "club",
            "city": "Sao Paulo",
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
            "weekday": "Sabado",
            "time": "09:00",
            "location": "Sala 2",
            "active": 1,
            "notes": "Treino semanal.",
        }
    )

    members = [
        {
            "name": "Ana",
            "surname": "Silva",
            "rating": "1680",
            "category": "Sub-18",
            "phone": "(11) 90000-0001",
            "email": "ana@example.com",
            "birth_date": "2010-03-12",
        },
        {
            "name": "Bruno",
            "surname": "Costa",
            "rating": "1740",
            "category": "Absoluto",
            "phone": "(11) 90000-0002",
            "email": "bruno@example.com",
            "birth_date": "1997-08-20",
        },
        {
            "name": "Carla",
            "surname": "Lima",
            "rating": "1605",
            "category": "Feminino",
            "phone": "(11) 90000-0003",
            "email": "carla@example.com",
            "birth_date": "2008-11-05",
        },
        {
            "name": "Diego",
            "surname": "Rocha",
            "rating": "1510",
            "category": "Sub-18",
            "phone": "(11) 90000-0004",
            "email": "diego@example.com",
            "birth_date": "2009-07-18",
        },
        {
            "name": "Elisa",
            "surname": "Mendes",
            "rating": "1820",
            "category": "Absoluto",
            "phone": "(11) 90000-0005",
            "email": "elisa@example.com",
            "birth_date": "1993-02-02",
        },
    ]
    member_ids = []
    for item in members:
        payload = {
            **item,
            "club_id": club_id,
            "class_id": class_id,
            "member_type": "aluno",
            "status": "active",
            "document": "",
            "guardian_name": "",
            "guardian_phone": "",
            "notes": "Cadastro de demonstracao.",
        }
        member_ids.append(member_service.create_member(payload))

    guardian_id = guardian_service.create_guardian(
        {
            "name": "Maria Silva",
            "phone": "(11) 98888-1111",
            "email": "maria@example.com",
            "document": "000.000.000-00",
            "address": "Rua das Torres, 64",
            "notes": "Responsavel pela Ana.",
            "active": 1,
        }
    )
    guardian_service.link_guardian_to_member(
        {
            "guardian_id": guardian_id,
            "member_id": member_ids[0],
            "relationship": "Mae",
            "primary_contact": 1,
            "emergency_contact": 1,
            "notes": "Contato principal.",
        }
    )

    session_id = training_service.save_session(
        {
            "club_id": club_id,
            "class_id": class_id,
            "title": "Treino de finais",
            "session_type": "aula",
            "session_date": "2026-05-16",
            "start_time": "09:00",
            "end_time": "11:00",
            "instructor": "Prof. Marcos",
            "location": "Sala 2",
            "status": "planned",
            "notes": "Finais de torre.",
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
        {
            "name": "Mensalidade aluno",
            "amount": "120",
            "billing_cycle": "monthly",
            "active": 1,
            "notes": "Plano padrao.",
        }
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
    finance_service.save_payment(
        {
            "member_id": member_ids[2],
            "plan_id": plan_id,
            "description": "Mensalidade abril",
            "reference_period": "2026-04",
            "due_date": "2026-04-10",
            "amount": "120",
            "status": "pending",
            "method": "",
            "notes": "Exemplo de atraso.",
        }
    )

    tournament_id = tournament_service.create_tournament(
        {
            "name": "Aberto Primavera",
            "scope": "club",
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
        tournament_id,
        {
            "name": "Aberto Primavera",
            "scope": "club",
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
            "chief_arbiter": "Arbitro Principal",
            "arbiters": "Equipe de apoio",
            "federation": "BRA",
            "state": "SP",
            "categories": "Absoluto, Sub-18, Feminino",
            "cutoff_date": "2026-05-18",
            "comments": "Torneio de demonstracao do manual.",
            "prizes": "Medalhas por categoria.",
            "initial_order": "rating",
            "tournament_type": "test",
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
    member_service.register_active_members_in_tournament(tournament_id)
    db.create_player(
        tournament_id,
        name="Felipe Andrade",
        surname="Andrade",
        given_name="Felipe",
        rating=1660,
        club="Convidado",
        category="Absoluto",
        fide_id="123456",
        cbx_id="654321",
    )

    first_round = pairing_service.generate_next_round(tournament_id)
    results = ["1-0", "0-1", "1/2-1/2"]
    for index, pairing in enumerate(db.get_pairings_for_round(first_round["id"])):
        if pairing["is_bye"]:
            continue
        pairing_service.update_result(tournament_id, pairing["id"], results[index % len(results)])
    pairing_service.close_round(tournament_id, first_round["id"])
    pairing_service.generate_next_round(tournament_id)

    event_service.save_event(
        {
            "club_id": club_id,
            "tournament_id": tournament_id,
            "title": "Aberto Primavera - rodada 2",
            "event_type": "tournament",
            "event_date": "2026-05-18",
            "start_time": "11:00",
            "end_time": "13:00",
            "location": "Salao principal",
            "status": "confirmed",
            "notes": "Evento vinculado ao torneio.",
        }
    )

    return tournament_id


def capture_screenshots(db: Database, tournament_id: int) -> dict[str, Path]:
    reset_screenshot_dir()
    pages = [
        ("clube", "Clube", "show_club"),
        ("membros", "Membros", "show_members"),
        ("responsaveis", "Responsaveis", "show_guardians"),
        ("aulas", "Aulas e presencas", "show_training"),
        ("financeiro", "Financeiro", "show_finance"),
        ("calendario", "Calendario", "show_calendar"),
        ("ranking_interno", "Ranking interno", "show_internal_ranking"),
        ("torneios", "Torneios", "show_tournaments"),
        ("config_torneio", "Configuracao do torneio", "show_tournament_settings"),
        ("jogadores", "Jogadores", "show_players"),
        ("rodadas", "Rodadas e resultados", "show_pairings"),
        ("classificacao", "Classificacao", "show_standings"),
        ("exportar", "Exportar", "show_export"),
        ("relatorios", "Relatorios", "show_reports"),
        ("config_app", "Configuracoes do app", "show_app_settings"),
    ]
    screenshots: dict[str, Path] = {}
    app: AlbericusApp | None = None
    try:
        app = AlbericusApp(db=db)
        app.geometry("1280x760+40+10")
        app.current_tournament_id = tournament_id
        app._set_current_tournament(tournament_id)
        app._show_info = lambda _message: None
        app._show_error = lambda exc: (_ for _ in ()).throw(exc)
        app.update()
        app.lift()
        app.attributes("-topmost", True)
        app.update()
        app.attributes("-topmost", False)
        time.sleep(0.3)

        for slug, _title, method_name in pages:
            getattr(app, method_name)()
            app.update_idletasks()
            app.update()
            time.sleep(0.25)
            screenshots[slug] = capture_window(app, slug)
    except TclError as exc:
        print(f"Captura de telas ignorada: Tk indisponivel ({exc})")
    finally:
        if app is not None:
            try:
                app.destroy()
            except Exception:
                pass
    return screenshots


def reset_screenshot_dir() -> None:
    if SCREENSHOT_DIR.exists():
        shutil.rmtree(SCREENSHOT_DIR)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def capture_window(app: AlbericusApp, slug: str) -> Path:
    left = app.winfo_rootx()
    top = app.winfo_rooty()
    width = app.winfo_width()
    height = app.winfo_height()
    image = ImageGrab.grab(bbox=(left, top, left + width, top + height))
    image = image.convert("RGB")
    path = SCREENSHOT_DIR / f"{slug}.jpg"
    image.save(path, quality=86, optimize=True)
    return path


def build_pdf(screenshots: dict[str, Path]) -> None:
    styles = create_styles()
    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.4 * cm,
        title="Manual de uso do Albericus",
        author="Albericus",
    )
    story = []
    today = date.today().strftime("%d/%m/%Y")

    story.append(Paragraph("Manual de uso do Albericus", styles["CoverTitle"]))
    story.append(Paragraph("Emparceiramento de xadrez e gestao simples de clube", styles["CoverSubtitle"]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(f"Gerado em {today}", styles["MutedCenter"]))
    story.append(Spacer(1, 1.0 * cm))
    story.append(
        Paragraph(
            "Este manual explica as telas principais do programa, o fluxo recomendado "
            "para criar torneios, registrar jogadores, gerar rodadas, lancar resultados, "
            "consultar classificacao, exportar arquivos e manter backups.",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("Fluxo rapido", styles["Heading1"]))
    story.append(
        bullet_list(
            [
                "Abra o Albericus.exe. Na primeira execucao, o programa cria o banco na pasta de dados do usuario.",
                "Cadastre o clube, escola ou turma em Clube.",
                "Cadastre membros e responsaveis antes de criar torneios integrados ao clube.",
                "Crie ou selecione um torneio em Torneios.",
                "Inclua jogadores em Jogadores, importando CSV ou inscrevendo membros cadastrados.",
                "Gere a rodada em Rodadas, salve todos os resultados e feche a rodada.",
                "Confira a Classificacao e gere exportacoes ou relatorios.",
                "Use Config. app para definir pastas e criar/restaurar backups.",
            ],
            styles,
        )
    )
    story.append(PageBreak())

    story.append(Paragraph("Visao geral da interface", styles["Heading1"]))
    story.append(
        Paragraph(
            "A barra lateral fica sempre a esquerda. Ela mostra o torneio selecionado e "
            "da acesso aos modulos do clube, torneio, relatorios e configuracoes. "
            "As telas de Jogadores, Rodadas, Classificacao e Exportar dependem de um torneio selecionado.",
            styles["Body"],
        )
    )
    story.append(screenshot_block("clube", "Tela inicial com painel do clube.", screenshots, styles))
    story.append(PageBreak())

    add_module(
        story,
        styles,
        screenshots,
        "Clube, Escolas e Turmas",
        "clube",
        "Use esta tela para cadastrar unidades, escolas parceiras e turmas. O painel superior resume membros, torneios, eventos e backups.",
        [
            "Preencha nome, cidade, endereco, telefone, e-mail, observacoes, tipo e status da unidade.",
            "Use Nova unidade para limpar o formulario e Salvar unidade para criar ou atualizar.",
            "Selecione uma unidade na lista para editar seus dados ou carregar as turmas vinculadas.",
            "Na area de turmas, informe nome, professor, dia, horario, local e status.",
        ],
        "Comece por aqui se o torneio sera ligado ao clube ou a uma turma.",
    )
    add_module(
        story,
        styles,
        screenshots,
        "Membros",
        "membros",
        "Membros sao socios, alunos, visitantes e convidados do clube. Eles podem ser inscritos diretamente em torneios integrados.",
        [
            "Cadastre nome, sobrenome, rating, categoria, contatos, documento, nascimento e observacoes.",
            "Defina tipo, status, clube/escola e turma.",
            "Use a busca e os filtros para localizar cadastros por tipo, status, categoria, clube ou turma.",
            "O historico mostra participacoes, resultados esportivos, presencas e financeiro do membro selecionado.",
        ],
        "Use status Ativo para membros que podem ser inscritos automaticamente em torneios.",
    )
    add_module(
        story,
        styles,
        screenshots,
        "Responsaveis",
        "responsaveis",
        "Guarda contatos de responsaveis e vincula esses contatos aos membros menores de idade.",
        [
            "Cadastre nome, telefone, e-mail, documento, endereco e observacoes.",
            "Depois de selecionar um responsavel, escolha o membro, informe parentesco e marque Principal ou Emergencia se necessario.",
            "A lista de alunos menores sem responsavel ajuda a encontrar cadastros incompletos.",
        ],
        "Mantenha os responsaveis atualizados para facilitar comunicacao administrativa.",
    )
    add_module(
        story,
        styles,
        screenshots,
        "Aulas e Presencas",
        "aulas",
        "Registra aulas, treinos e eventos de formacao, com chamada por membro.",
        [
            "Informe titulo, data, horario, instrutor, local, tipo, status, clube e turma.",
            "Selecione uma aula para carregar a chamada.",
            "Marque presenca individualmente ou use Todos presentes para acelerar a rotina.",
            "As presencas alimentam relatorios de membro, clube e pacote administrativo.",
        ],
        "As datas nesta tela usam o formato AAAA-MM-DD.",
    )
    add_module(
        story,
        styles,
        screenshots,
        "Financeiro",
        "financeiro",
        "Controla planos, mensalidades, lancamentos e pendencias.",
        [
            "Crie planos com nome, valor, ciclo, status ativo e observacoes.",
            "Lance pagamentos por membro, plano, referencia, vencimento, data de pagamento, valor, metodo e status.",
            "Use os filtros por texto, periodo e status para consultar pendencias.",
            "Os cards de resumo mostram recebido, pendente, atrasado, pagos e atrasos.",
        ],
        "Lancamentos pendentes com vencimento passado aparecem como atrasados nos resumos.",
    )
    add_module(
        story,
        styles,
        screenshots,
        "Calendario",
        "calendario",
        "Organiza eventos do clube e permite vincular torneios ao calendario.",
        [
            "Cadastre titulo, data, horario, local, tipo, status, clube e torneio vinculado.",
            "Use a busca por titulo, local, clube ou torneio.",
            "Filtre por periodo e status para acompanhar eventos planejados, confirmados, concluidos ou cancelados.",
        ],
        "Eventos vinculados ajudam a manter agenda e torneios no mesmo fluxo.",
    )
    add_module(
        story,
        styles,
        screenshots,
        "Ranking Interno",
        "ranking_interno",
        "Mostra rating, variacao, partidas, aproveitamento, resultado acumulado e ultima performance dos membros.",
        [
            "Filtre por categoria, status e busca textual.",
            "Use Aplicar torneio atual depois de um torneio concluido ou com rodadas fechadas para atualizar rating interno.",
            "Use Historico para ver mudancas anteriores do membro selecionado.",
            "Use Exportar para gerar arquivo do ranking.",
        ],
        "Convidados externos do torneio nao entram como membros no ranking interno.",
    )

    story.append(PageBreak())
    add_module(
        story,
        styles,
        screenshots,
        "Torneios",
        "torneios",
        "Cria torneios e define qual torneio esta ativo para as demais telas.",
        [
            "Informe nome, local, datas, quantidade de rodadas, ritmo e pontos do bye.",
            "Escolha o escopo: Avulso, Clube/Escola ou Turma.",
            "Use Criar torneio para salvar; depois selecione uma linha e clique Selecionar torneio.",
            "O torneio selecionado aparece na barra lateral.",
        ],
        "Sem torneio selecionado, Jogadores, Rodadas, Classificacao e Exportar ficam bloqueados.",
    )
    add_module(
        story,
        styles,
        screenshots,
        "Configuracao do Torneio",
        "config_torneio",
        "Reune dados oficiais, regras, flags de interface/publicacao e agenda de rodadas.",
        [
            "Edite dados gerais: nome, local, datas, rodadas, ritmo, bye, escopo, clube e turma.",
            "Preencha campos oficiais como FIDE Event-ID, organizador, pagina, arbitros, federacao, categorias e premiacao.",
            "Defina ordem inicial, tipo de torneio, pontos de entrada tardia e flags como desativar bye ou ocultar classificacao.",
            "Configure data e horario de cada rodada na agenda.",
        ],
        "Mudancas perigosas liberam alteracoes em rodada fechada; use somente quando for realmente necessario.",
    )
    add_module(
        story,
        styles,
        screenshots,
        "Jogadores",
        "jogadores",
        "Controla os participantes do torneio selecionado.",
        [
            "Adicione convidados manualmente com dados esportivos, IDs FIDE/CBX, ratings, clube e categoria.",
            "Inscreva membros do clube ou da turma quando o torneio tiver escopo integrado.",
            "Use Importar CSV para cadastrar varios jogadores de uma vez.",
            "Use Atualizar oficiais para preencher dados a partir da base oficial importada.",
            "Defina status no torneio: Ativo, Desistente, Ausente ou Nao emparceirado.",
        ],
        "Apenas jogadores ativos entram nas proximas rodadas.",
    )
    add_module(
        story,
        styles,
        screenshots,
        "Rodadas e Resultados",
        "rodadas",
        "Gera emparceiramentos, registra resultados e fecha rodadas.",
        [
            "Clique Gerar proxima rodada para criar a primeira rodada por rating ou a proxima pelo sistema suico simplificado.",
            "Selecione a rodada no menu e uma mesa na tabela.",
            "Escolha o resultado e clique Salvar resultado.",
            "Use Trocar cores ou Trocar jogador para ajustes antes do fechamento.",
            "Clique Fechar rodada somente depois de preencher todos os resultados finais.",
        ],
        "Ao fechar uma rodada, o sistema cria backup automatico antes de gravar o fechamento.",
    )
    add_module(
        story,
        styles,
        screenshots,
        "Classificacao",
        "classificacao",
        "Mostra pontuacao e criterios de desempate do torneio selecionado.",
        [
            "Use Recalcular para atualizar a tabela.",
            "Filtre por categoria quando houver categorias cadastradas.",
            "A tabela exibe pontos, Buchholz, Buchholz mediano, Sonneborn-Berger, vitorias, performance, rating e clube.",
            "Use Atualizar rating interno para aplicar os resultados ao ranking dos membros.",
        ],
        "Se a flag Ocultar classificacao estiver ativa, esta tela mostra apenas o aviso.",
    )
    add_module(
        story,
        styles,
        screenshots,
        "Exportar",
        "exportar",
        "Gera arquivos do torneio selecionado.",
        [
            "Escolha Completo, Classificacao, Rodada especifica, Todas as rodadas, Jogadores ou Site HTML.",
            "Para arquivos, escolha csv, xlsx ou pdf.",
            "Para Rodada especifica, selecione a rodada desejada.",
            "Para Site HTML, escolha uma pasta; o sistema gera um pacote estatico para publicacao.",
        ],
        "A pasta padrao de exportacao pode ser alterada em Config. app.",
    )
    add_module(
        story,
        styles,
        screenshots,
        "Relatorios",
        "relatorios",
        "Gera relatorios administrativos do clube, de membros e por periodo.",
        [
            "Escolha Geral do clube, Membro individual, Torneios por periodo, Presencas, Financeiro, Eventos, Ranking interno ou Pacote administrativo.",
            "Escolha o formato csv, xlsx ou pdf.",
            "Quando o relatorio exigir periodo, informe inicio e fim no formato AAAA-MM-DD.",
            "No relatorio individual, selecione o membro desejado.",
        ],
        "Use Pacote administrativo para uma visao consolidada do clube.",
    )
    add_module(
        story,
        styles,
        screenshots,
        "Configuracoes do Aplicativo",
        "config_app",
        "Define preferencias locais e rotinas de backup.",
        [
            "Escolha aparencia Sistema, Claro ou Escuro.",
            "Defina a pasta padrao de exportacao.",
            "Defina a pasta de backups.",
            "Use Criar backup agora antes de operacoes importantes.",
            "Use Restaurar selecionado para voltar a um backup; o sistema cria uma copia de seguranca antes de restaurar.",
        ],
        "O banco local fica na pasta de dados do usuario. No Windows, o padrao e %LOCALAPPDATA%\\Albericus.",
    )

    story.append(PageBreak())
    story.append(Paragraph("Regras importantes", styles["Heading1"]))
    story.append(
        bullet_list(
            [
                "Fechar rodada exige todos os resultados preenchidos: 1-0, 0-1, 1/2-1/2, 1F-0F, 0F-1F, 0F-0F ou BYE.",
                "Rodada fechada fica protegida. Para alterar resultado fechado, habilite Mudancas perigosas na configuracao do torneio.",
                "Se o bye estiver desativado, o torneio precisa ter numero par de jogadores ativos.",
                "Jogador desistente, ausente ou nao emparceirado permanece no historico, mas nao entra normalmente nas novas rodadas.",
                "Entrada tardia pode receber pontos configurados em Pontos por adesao tardia.",
                "Backups automaticos sao criados antes do fechamento de rodada e antes de restauracoes.",
                "Ao entregar apenas Albericus.exe, o programa cria banco, logs e pastas de trabalho na primeira execucao.",
            ],
            styles,
        )
    )
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("Problemas comuns", styles["Heading1"]))
    data = [
        ["Situacao", "O que verificar"],
        ["Nao consigo gerar rodada", "Cadastre pelo menos 2 jogadores ativos e feche/exclua rodada anterior aberta."],
        ["Torneio nao aparece nas telas", "Selecione o torneio na tela Torneios."],
        ["Classificacao vazia", "Confira se ha jogadores e se resultados foram salvos/rodadas fechadas."],
        ["Erro ao exportar", "Verifique permissao da pasta e se o arquivo nao esta aberto em outro programa."],
        ["Preciso voltar dados", "Use Config. app > Restaurar selecionado com um backup valido."],
    ]
    table = Table(data, colWidths=[5.0 * cm, 11.0 * cm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(table)

    doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)


def create_styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "CoverTitle": ParagraphStyle(
            "CoverTitle",
            parent=sample["Title"],
            fontName="Helvetica-Bold",
            fontSize=28,
            leading=34,
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
            fontSize=18,
            leading=23,
            textColor=colors.HexColor("#0F172A"),
            spaceBefore=8,
            spaceAfter=8,
        ),
        "Heading2": ParagraphStyle(
            "Heading2",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#1E293B"),
            spaceBefore=8,
            spaceAfter=5,
        ),
        "Body": ParagraphStyle(
            "Body",
            parent=sample["BodyText"],
            fontSize=9.8,
            leading=13.5,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=6,
        ),
        "Small": ParagraphStyle(
            "Small",
            parent=sample["BodyText"],
            fontSize=8.5,
            leading=11.5,
            textColor=colors.HexColor("#475569"),
            spaceAfter=5,
        ),
    }


def add_module(
    story: list,
    styles: dict[str, ParagraphStyle],
    screenshots: dict[str, Path],
    title: str,
    slug: str,
    overview: str,
    bullets: list[str],
    note: str,
) -> None:
    story.append(Paragraph(title, styles["Heading1"]))
    story.append(Paragraph(overview, styles["Body"]))
    story.append(bullet_list(bullets, styles))
    story.append(Paragraph(f"<b>Observacao:</b> {note}", styles["Small"]))
    story.append(screenshot_block(slug, f"Print: {title}.", screenshots, styles))
    story.append(PageBreak())


def bullet_list(items: list[str], styles: dict[str, ParagraphStyle]) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(item, styles["Body"]), leftIndent=8) for item in items],
        bulletType="bullet",
        leftIndent=14,
        bulletFontName="Helvetica",
        bulletFontSize=8,
        bulletColor=colors.HexColor("#2563EB"),
        spaceAfter=8,
    )


def screenshot_block(
    slug: str,
    caption: str,
    screenshots: dict[str, Path],
    styles: dict[str, ParagraphStyle],
):
    path = screenshots.get(slug)
    if not path or not path.exists():
        return Paragraph("Print de tela nao disponivel nesta geracao.", styles["Small"])
    max_width = 17.2 * cm
    with PILImage.open(path) as image:
        width, height = image.size
    ratio = max_width / width
    flowable = Image(str(path), width=max_width, height=height * ratio)
    return KeepTogether(
        [
            Spacer(1, 0.2 * cm),
            flowable,
            Paragraph(caption, styles["Small"]),
        ]
    )


def draw_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawString(1.5 * cm, 0.75 * cm, "Albericus - Manual de uso")
    canvas.drawRightString(A4[0] - 1.5 * cm, 0.75 * cm, f"Pagina {doc.page}")
    canvas.restoreState()


if __name__ == "__main__":
    main()
