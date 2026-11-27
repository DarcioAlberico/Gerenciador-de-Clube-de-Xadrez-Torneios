"""Lint de acentuação nos textos visíveis da interface (F5.12 / P3-15).

A F3.5 corrigiu 93 rótulos e não deixou nada que impedisse a volta — e a
auditoria de 2026-07-29 achou ~26 palavras sem acento de novo, a começar pela
tela Início ("Inicio", "acao", "pendencia"). Um lint resolve; a pergunta era
qual regra ele aplica.

**A regra é a auto-consistência**, não um dicionário. O app é quem diz como se
escreve cada palavra: se "Classificação" aparece no catálogo e "Classificacao"
aparece numa tela, a segunda está errada — e isso vale sem manter lista de
palavras portuguesas, sem depender de biblioteca, e melhora sozinho a cada
texto novo escrito direito.

O corpus é o **texto que o usuário vê**: os valores do catálogo
(`i18n/pt_BR.json`) mais os literais passados a ``text=``, ``label=``,
``placeholder_text=``, ``help_text=`` e afins em ``src/ui``. Comentário e nome
de variável ficam de fora de propósito — o app é PT-BR na tela e ASCII no
código, e misturar as duas coisas faria o lint brigar com a convenção.

Uma segunda regra (RGS-27) completa a primeira: uma **lista fechada** de
palavras que nunca se escrevem sem acento, cobrada em todo literal de
``src/ui`` — ver ``PALAVRAS_SEM_ACENTO``.

Uso:
    python scripts/check_ui_accents.py            # reprova o que estiver torto
    python scripts/check_ui_accents.py --lista    # só lista os suspeitos
"""
from __future__ import annotations

import ast
import json
import re
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
UI = RAIZ / "src" / "ui"
CATALOGO = RAIZ / "i18n" / "pt_BR.json"

# Atributos cujo valor vai para a tela. `title=` entra porque é o título da
# janela; `tip=` porque o tooltip e texto tanto quanto o rótulo.
ATRIBUTOS_VISIVEIS = {
    "text",
    "label",
    "title",
    "placeholder_text",
    "help_text",
    "empty_title",
    "empty_description",
    "tip",
    "message",
    "busy_message",
    "confirm_text",
    "cancel_text",
    "close_text",
}

# Texto visível também chega por argumento POSICIONAL, e foi por ai que a
# primeira versão deste lint deixou passar a tela de Configurações do app
# inteira: `_page_title("Configurações do aplicativo", "Ajuste preferências
# locais...")` nao tem nenhum `text=`. Aqui ficam as funções de UI cujo
# posicional e texto — nome da função -> índices dos argumentos.
POSICIONAIS_VISIVEIS = {
    "_page_title": (0, 1),
    "_section_title": (1,),
    "primary_button": (1,),
    "secondary_button": (1,),
    "neutral_button": (1,),
    "danger_button": (1,),
    "section": (0,),
    "note": (0,),
    "text": (0,),
    "select": (0,),
    "date": (0,),
    "area": (0,),
    "field": (0,),
    "labeled_field": (1,),
    "_show_info": (0,),
    "_show_warning": (0,),
    "_show_error": (),  # recebe exceção, não texto
    "_show_report": (0, 1),
    "_show_toast": (0,),
    "confirm_dialog": (1, 2),
    "alert_dialog": (1, 2),
    "tri_state_dialog": (1, 2),
    "report_dialog": (1, 2),
    "choice_dialog": (1, 2),
    "Dialog": (1,),
    "Tooltip": (1,),
    "modal": (1,),
    "close_button": (1,),
}

# Tabela de campos: `[("address", "Endereco"), ...]` — o rótulo só vira `text=`
# muitas linhas depois, dentro do laço que monta o formulário. Reconhecida pela
# forma: primeiro elemento com cara de CHAVE (`^[a-z][a-z0-9_]*$`) e segundo com
# cara de RÓTULO (tem espaço ou começa com maiúscula). Restrito assim de
# propósito: uma lista de nomes de ícone ("calendario", "integracoes") não passa
# no teste do rótulo, e o app e ASCII no código — o lint não pode brigar com
# isso.
_CHAVE_DE_CAMPO = re.compile(r"^[a-z][a-z0-9_]*$")


def _parece_rotulo(texto: str) -> bool:
    return bool(texto) and (" " in texto or texto[0].isupper())


# Cabeçalho de tabela chega como DICIONÁRIO (`{"action": "Acao"}`) no terceiro
# posicional do `_make_tree`. Sem isto, "Acao" e "Descricao" passavam batido —
# e cabeçalho de coluna e dos textos mais lidos da tela.
DICIONARIOS_VISIVEIS = {"_make_tree": (2,)}

# Palavras em que **as duas grafias existem** em português, e por isso a
# auto-consistencia não decide: "esta mesa" x "esta pronto", "eu publico" x
# "publico alvo". Cada entrada e uma decisão, não uma isenção preguiçosa.
HOMOGRAFOS = {
    "esta",  # demonstrativo x verbo estar
    "publico",  # verbo publicar x adjetivo/substantivo
    "continua",  # verbo continuar x adjetivo continua
    "duvida",  # verbo duvidar x substantivo duvida
    "pratica",  # verbo praticar x substantivo pratica
    "secretaria",  # cargo x lugar
    "sabia",  # verbo saber x adjetivo sabia
    "critica",  # verbo criticar x substantivo crítica
    "analise",  # verbo analisar (imperativo) x substantivo analise
    "medico",  # raro, mas o par existe
    "fabrica",  # verbo fabricar x substantivo fabrica
}

# O verbo com pronome ("gravá-lo") fica de fora: o acento é do infinitivo, não
# do presente "grava"; quem confere essa forma é _VERBO_COM_PRONOME.
_PALAVRA = re.compile(r"[A-Za-zÀ-ÿ]{4,}(?![A-Za-zÀ-ÿ]|-l[oa]s?\b)")

# `{codigo}` num texto do catálogo NÃO é palavra visível: e o **nome do
# parâmetro** que o `t(chave, codigo=...)` preenche. Acentuar ali quebra a
# chamada — e foi exatamente o que a primeira versão deste lint tentou fazer.
_PLACEHOLDER = re.compile(r"\{[^{}]*\}")


def _visivel(texto: str) -> str:
    """O texto sem os campos de substituição — só o que o usuário lê."""
    return _PLACEHOLDER.sub(" ", texto)


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")


def _textos_do_catalogo() -> list[tuple[str, str]]:
    """Valores do catálogo, **menos** as chaves de busca.

    ``nav.*.keywords`` não é texto que se lê: é o que o usuário **digita** no
    command palette. Escrever "classificacao" ali é o comportamento correto —
    quem procura sem acento tem de achar. Cobrar acento nessas chaves seria o
    lint brigando com o propósito delas.
    """
    if not CATALOGO.is_file():  # pragma: no cover - repo sem catalogo
        return []
    dados = json.loads(CATALOGO.read_text(encoding="utf-8"))
    return [
        (f"i18n/pt_BR.json:{chave}", str(valor))
        for chave, valor in dados.items()
        if not chave.endswith(".keywords")
    ]


def _textos_do_codigo() -> list[tuple[str, str]]:
    achados: list[tuple[str, str]] = []
    for arquivo in sorted(UI.rglob("*.py")):
        try:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - arquivo em edicao
            continue
        nome = arquivo.relative_to(RAIZ).as_posix()
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            for palavra_chave in no.keywords:
                if palavra_chave.arg not in ATRIBUTOS_VISIVEIS:
                    continue
                valor = palavra_chave.value
                if isinstance(valor, ast.Constant) and isinstance(valor.value, str):
                    achados.append((f"{nome}:{valor.lineno}", valor.value))

            chamada = no.func.id if isinstance(no.func, ast.Name) else getattr(no.func, "attr", "")
            for indice in POSICIONAIS_VISIVEIS.get(chamada, ()):
                if indice >= len(no.args):
                    continue
                valor = no.args[indice]
                if isinstance(valor, ast.Constant) and isinstance(valor.value, str):
                    achados.append((f"{nome}:{valor.lineno}", valor.value))
            for indice in DICIONARIOS_VISIVEIS.get(chamada, ()):
                if indice >= len(no.args):
                    continue
                valor = no.args[indice]
                if not isinstance(valor, ast.Dict):
                    continue
                for item in valor.values:
                    if isinstance(item, ast.Constant) and isinstance(item.value, str):
                        achados.append((f"{nome}:{item.lineno}", item.value))

        for no in ast.walk(arvore):
            if not isinstance(no, ast.Tuple) or len(no.elts) < 2:
                continue
            chave, rotulo = no.elts[0], no.elts[1]
            if not (isinstance(chave, ast.Constant) and isinstance(chave.value, str)):
                continue
            if not (isinstance(rotulo, ast.Constant) and isinstance(rotulo.value, str)):
                continue
            if _CHAVE_DE_CAMPO.match(chave.value) and _parece_rotulo(rotulo.value):
                achados.append((f"{nome}:{rotulo.lineno}", rotulo.value))
    return achados


def corpus() -> list[tuple[str, str]]:
    """``(origem, texto)`` de tudo que o usuário lê na interface."""
    return _textos_do_catalogo() + _textos_do_codigo()


def grafias_acentuadas(textos: list[tuple[str, str]]) -> dict[str, set[str]]:
    """Palavra sem acento → grafias **acentuadas** que o próprio app usa."""
    mapa: dict[str, set[str]] = {}
    for _origem, texto in textos:
        for palavra in _PALAVRA.findall(_visivel(texto)):
            if _sem_acento(palavra) != palavra:
                mapa.setdefault(_sem_acento(palavra).lower(), set()).add(palavra)
    return mapa


def checar_acentos() -> list[str]:
    """Palavras que o app escreve acentuadas em um lugar e sem acento em outro."""
    textos = corpus()
    acentuadas = grafias_acentuadas(textos)
    problemas: list[str] = []
    for origem, texto in textos:
        for palavra in _PALAVRA.findall(_visivel(texto)):
            chave = palavra.lower()
            if _sem_acento(palavra) != palavra or chave in HOMOGRAFOS:
                continue
            certas = acentuadas.get(chave)
            if not certas:
                continue
            problemas.append(
                f"{origem}: '{palavra}' sem acento — o app escreve "
                f"{sorted(certas)} em outro lugar (P3-15/F5.12)."
            )
    return problemas


# --- RGS-27: lista fechada -------------------------------------------------
#
# A auto-consistencia acima só pega a palavra que o app JÁ escreve certa em
# algum texto visível, e só olha os argumentos que sabe que vão para a tela.
# "Pre-visualizar proxima rodada" passou pelas duas frestas: o rótulo vinha de
# uma tupla `(texto, comando)` e ninguém escrevia "próxima" num `text=`.
#
# Esta segunda regra é o oposto: uma LISTA FECHADA de palavras portuguesas
# comuns que nunca se escrevem sem acento, cobrada em TODO literal de string
# de `src/ui` e no catálogo. Cada palavra entrou porque foi achada sem acento
# num texto de tela (RGS-27). Homógrafo ("esta", "publico", "secretaria")
# não entra: a lista só tem palavra cuja forma sem acento não existe.
PALAVRAS_SEM_ACENTO: dict[str, str] = {
    "acao": "ação",
    "aceleracao": "aceleração",
    "adesao": "adesão",
    "adversario": "adversário",
    "adversarios": "adversários",
    "advertencia": "advertência",
    "agua": "água",
    "album": "álbum",
    "alem": "além",
    "alguem": "alguém",
    "ambar": "âmbar",
    "anotacao": "anotação",
    "aparecerao": "aparecerão",
    "apos": "após",
    "aprovacao": "aprovação",
    "aquisicao": "aquisição",
    "arbitro": "árbitro",
    "arbitros": "árbitros",
    "ardosia": "ardósia",
    "areas": "áreas",
    "ate": "até",
    "atencao": "atenção",
    "ausencia": "ausência",
    "automatica": "automática",
    "automatico": "automático",
    "avanca": "avança",
    "avancadas": "avançadas",
    "avancado": "avançado",
    "avanco": "avanço",
    "basico": "básico",
    "basicos": "básicos",
    "bonus": "bônus",
    "botoes": "botões",
    "cabecalho": "cabeçalho",
    "calculo": "cálculo",
    "calendario": "calendário",
    "campeoes": "campeões",
    "capitao": "capitão",
    "cartoes": "cartões",
    "catalogo": "catálogo",
    "celulas": "células",
    "ceu": "céu",
    "classica": "clássica",
    "classico": "clássico",
    "classificacao": "classificação",
    "cobranca": "cobrança",
    "cobrancas": "cobranças",
    "codigo": "código",
    "codigos": "códigos",
    "colocacao": "colocação",
    "colombia": "colômbia",
    "comecar": "começar",
    "compativeis": "compatíveis",
    "compativel": "compatível",
    "competicao": "competição",
    "comunicacao": "comunicação",
    "concluida": "concluída",
    "concluido": "concluído",
    "concluidos": "concluídos",
    "conclusao": "conclusão",
    "conexao": "conexão",
    "conferencia": "conferência",
    "configuracoes": "configurações",
    "configuravel": "configurável",
    "conteudo": "conteúdo",
    "coordenacao": "coordenação",
    "correcao": "correção",
    "criterio": "critério",
    "criterios": "critérios",
    "critico": "crítico",
    "decisao": "decisão",
    "dedicacao": "dedicação",
    "deducao": "dedução",
    "descricao": "descrição",
    "desfaca": "desfaça",
    "desistencia": "desistência",
    "destinatario": "destinatário",
    "devolucao": "devolução",
    "diagnostico": "diagnóstico",
    "diferencas": "diferenças",
    "direcao": "direção",
    "disponiveis": "disponíveis",
    "disponivel": "disponível",
    "distribuicao": "distribuição",
    "distribuido": "distribuído",
    "distribuidos": "distribuídos",
    "divisao": "divisão",
    "duracao": "duração",
    "edicao": "edição",
    "eletronico": "eletrônico",
    "emergencia": "emergência",
    "emissao": "emissão",
    "emissoes": "emissões",
    "emprestimo": "empréstimo",
    "emprestimos": "empréstimos",
    "endereco": "endereço",
    "entao": "então",
    "escalacao": "escalação",
    "escalacoes": "escalações",
    "esforco": "esforço",
    "estao": "estão",
    "estatistica": "estatística",
    "estrategicos": "estratégicos",
    "evitavel": "evitável",
    "evolucao": "evolução",
    "excecao": "exceção",
    "excluida": "excluída",
    "exclusao": "exclusão",
    "exercicio": "exercício",
    "exportacao": "exportação",
    "expulsao": "expulsão",
    "facil": "fácil",
    "federacao": "federação",
    "federacoes": "federações",
    "ficticios": "fictícios",
    "formulario": "formulário",
    "fracao": "fração",
    "funcao": "função",
    "genero": "gênero",
    "geracao": "geração",
    "grafica": "gráfica",
    "ha": "há",
    "historico": "histórico",
    "horario": "horário",
    "ilegivel": "ilegível",
    "impar": "ímpar",
    "importacao": "importação",
    "importavel": "importável",
    "impressao": "impressão",
    "indigo": "índigo",
    "indisponivel": "indisponível",
    "inevitavel": "inevitável",
    "informacao": "informação",
    "inicio": "início",
    "inscricao": "inscrição",
    "instrucao": "instrução",
    "integracoes": "integrações",
    "intermediario": "intermediário",
    "invalida": "inválida",
    "invalidas": "inválidas",
    "invalido": "inválido",
    "invalidos": "inválidos",
    "inventario": "inventário",
    "italia": "itália",
    "ja": "já",
    "la": "lá",
    "lanca": "lança",
    "lancada": "lançada",
    "lancado": "lançado",
    "lancamento": "lançamento",
    "lancamentos": "lançamentos",
    "lancar": "lançar",
    "mantem": "mantém",
    "manutencao": "manutenção",
    "maximo": "máximo",
    "medio": "médio",
    "metodo": "método",
    "migracao": "migração",
    "minimo": "mínimo",
    "mudanca": "mudança",
    "mudancas": "mudanças",
    "nao": "não",
    "niveis": "níveis",
    "nivel": "nível",
    "notificacao": "notificação",
    "notificacoes": "notificações",
    "numerico": "numérico",
    "numero": "número",
    "numeros": "números",
    "obrigatoria": "obrigatória",
    "obrigatorio": "obrigatório",
    "observacoes": "observações",
    "opcoes": "opções",
    "organizacao": "organização",
    "orientacao": "orientação",
    "padrao": "padrão",
    "pagina": "página",
    "paineis": "painéis",
    "parametrizavel": "parametrizável",
    "participacao": "participação",
    "pedagogico": "pedagógico",
    "pendencia": "pendência",
    "pendencias": "pendências",
    "periodo": "período",
    "permissao": "permissão",
    "perturbacao": "perturbação",
    "podio": "pódio",
    "politica": "política",
    "polonia": "polônia",
    "pontuacao": "pontuação",
    "possivel": "possível",
    "poster": "pôster",
    "pre": "pré",
    "preferencia": "preferência",
    "premiacao": "premiação",
    "premio": "prêmio",
    "premios": "prêmios",
    "presenca": "presença",
    "presencas": "presenças",
    "previa": "prévia",
    "principios": "princípios",
    "proprio": "próprio",
    "proxima": "próxima",
    "proximo": "próximo",
    "proximos": "próximos",
    "rapidas": "rápidas",
    "reconheciveis": "reconhecíveis",
    "referencia": "referência",
    "relatorio": "relatório",
    "relatorios": "relatórios",
    "relogio": "relógio",
    "relogios": "relógios",
    "repeticao": "repetição",
    "responsaveis": "responsáveis",
    "responsavel": "responsável",
    "restricao": "restrição",
    "retencao": "retenção",
    "reuniao": "reunião",
    "rodape": "rodapé",
    "rodizio": "rodízio",
    "saida": "saída",
    "sancao": "sanção",
    "sao": "são",
    "saudacao": "saudação",
    "secao": "seção",
    "secundario": "secundário",
    "seguranca": "segurança",
    "senao": "senão",
    "sepia": "sépia",
    "sera": "será",
    "serao": "serão",
    "servico": "serviço",
    "silencio": "silêncio",
    "simultanea": "simultânea",
    "sincronizacao": "sincronização",
    "socio": "sócio",
    "socios": "sócios",
    "submissao": "submissão",
    "submissoes": "submissões",
    "substituicao": "substituição",
    "substituicoes": "substituições",
    "substituido": "substituído",
    "suico": "suíço",
    "sumulas": "súmulas",
    "tambem": "também",
    "taticas": "táticas",
    "temporario": "temporário",
    "termino": "término",
    "titulos": "títulos",
    "tolerancia": "tolerância",
    "transacao": "transação",
    "ultima": "última",
    "ultimos": "últimos",
    "unico": "único",
    "usuario": "usuário",
    "validacao": "validação",
    "valido": "válido",
    "validos": "válidos",
    "variacao": "variação",
    "verificacao": "verificação",
    "verificavel": "verificável",
    "versao": "versão",
    "vinculo": "vínculo",
    "visao": "visão",
    "visualizacao": "visualização",
    "vitoria": "vitória",
    "vitorias": "vitórias",
}

# Literal que não é texto de tela: chamada de log (o log é ASCII de propósito)
# e as funções que recebem nome, chave ou caminho em vez de texto.
_METODOS_DE_LOG = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}
# Nome da função -> índice do argumento que é chave/nome de atributo.
_CHAMADAS_DE_CHAVE = {
    "get": 0,
    "pop": 0,
    "setdefault": 0,
    "cget": 0,
    "startswith": 0,
    "endswith": 0,
    "getattr": 1,
    "hasattr": 1,
    "setattr": 1,
}
_CHAVES_DE_BUSCA = {"synonyms", "keywords"}
_SQL = re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|WITH|PRAGMA)\b", re.IGNORECASE)
# `"proxima_rodada"`, `"nav.club"`, `"calendario"`: cara de chave, não de frase.
_CARA_DE_CHAVE = re.compile(r"^[a-z][a-z0-9_.\-]*$")
# `"15-calendario.png"`, `"_sumulas.pdf"`, `";bonus="`: nome de arquivo ou
# fragmento técnico — sem espaço e com pontuação de código.
_CARA_DE_TECNICO = re.compile(r"^\S*[_/\\=;]\S*$|^\S+\.[A-Za-z0-9]{2,4}$")
# Palavra inteira: "arbitro01" (exemplo de login) e "nao_existe" não são texto.
_PALAVRA_INTEIRA = re.compile(r"(?<!\w)[A-Za-zÀ-ÿ]+(?!\w)")
# Infinitivo em -ar/-er perde o "r" e ganha acento antes do pronome (gravá-lo,
# preenchê-la); em -ir não leva (emiti-lo).
_PRONOMES_ENCLITICOS = {"lo", "la", "los", "las"}
_VERBO_COM_PRONOME = re.compile(r"(?<!\w)([A-Za-zÀ-ÿ]{2,})([ae])-(lo|la|los|las)(?!\w)")
_ACENTO_DO_INFINITIVO = {"a": "á", "e": "ê"}


def _eh_chamada_de_log(chamada: ast.Call) -> bool:
    funcao = chamada.func
    if not isinstance(funcao, ast.Attribute) or funcao.attr not in _METODOS_DE_LOG:
        return False
    # `logger.info`, `self.logger.info`, `logging.getLogger(x).info`.
    return "log" in ast.unparse(funcao.value).lower()


def _constantes_fora_da_tela(arvore: ast.AST) -> set[int]:
    """``id()`` das constantes que nao vao para a tela, por posicao na arvore."""
    fora: set[int] = set()

    def marcar(no: ast.AST | None) -> None:
        if no is None:
            return
        for filho in ast.walk(no):
            if isinstance(filho, ast.Constant):
                fora.add(id(filho))

    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            corpo = no.body
            if corpo and isinstance(corpo[0], ast.Expr) and isinstance(corpo[0].value, ast.Constant):
                marcar(corpo[0])  # docstring
        elif isinstance(no, ast.Call):
            if _eh_chamada_de_log(no):
                marcar(no)
                continue
            nome = no.func.id if isinstance(no.func, ast.Name) else getattr(no.func, "attr", "")
            indice = _CHAMADAS_DE_CHAVE.get(nome)
            if indice is not None and len(no.args) > indice:
                marcar(no.args[indice])
        elif isinstance(no, ast.Dict):
            for chave, valor in zip(no.keys, no.values):
                marcar(chave)
                # Sinônimo e o que chega no cabeçalho do arquivo do usuário:
                # termo de busca, como o `.keywords` do catálogo — não se lê.
                if isinstance(chave, ast.Constant) and chave.value in _CHAVES_DE_BUSCA:
                    marcar(valor)
        elif isinstance(no, ast.Subscript):
            marcar(no.slice)
        elif isinstance(no, ast.Compare):
            for operando in [no.left, *no.comparators]:
                marcar(operando)
    return fora


def literais_de_tela() -> list[tuple[str, str]]:
    """``(origem, texto)`` de todo literal de `src/ui` que pode chegar à tela.

    Mais largo que :func:`corpus`: não depende de saber o nome do argumento.
    Fica de fora o que comprovadamente não é texto de tela — docstring, log,
    chave de dicionário, índice, comparação, SQL e literal com cara de chave.
    """
    achados: list[tuple[str, str]] = []
    for arquivo in sorted(UI.rglob("*.py")):
        nome = arquivo.relative_to(RAIZ).as_posix()
        achados.extend(literais_do_fonte(arquivo.read_text(encoding="utf-8"), nome))
    return achados


def literais_do_fonte(fonte: str, nome: str) -> list[tuple[str, str]]:
    """Os literais de tela de UM arquivo-fonte (ver :func:`literais_de_tela`)."""
    try:
        arvore = ast.parse(fonte)
    except SyntaxError:  # pragma: no cover - arquivo em edicao
        return []
    fora = _constantes_fora_da_tela(arvore)
    achados: list[tuple[str, str]] = []
    for no in ast.walk(arvore):
        if not (isinstance(no, ast.Constant) and isinstance(no.value, str)) or id(no) in fora:
            continue
        if _parece_texto(no.value):
            achados.append((f"{nome}:{no.lineno}", no.value))
    return achados


def _parece_texto(texto: str) -> bool:
    """Literal com cara de frase — não vazio, nem chave, nem técnico, nem SQL."""
    return bool(texto.strip()) and not (
        _CARA_DE_CHAVE.match(texto) or _CARA_DE_TECNICO.match(texto) or _SQL.match(texto)
    )


# --- Texto de tela que nasce em src/services -------------------------------
#
# A lista fechada lia só `src/ui`, e o serviço também escreve na tela: a
# mensagem de toda recusa (a tela mostra `str(exc)` — ver `_classify_error`),
# os rótulos de constants.py, os alertas do painel. Ler TODO literal de
# `src/services` não serve: ali mora valor gravado no banco, chave de TRF,
# nome de coluna. O critério e o que comprovadamente vai para a tela:
#
# 1. mensagem de exceção: todo literal dentro de ``AppError(...)``,
#    ``ValueError(...)`` e ``PermissionError(...)`` (``EXCECOES_DE_TELA``);
# 2. tabela de rótulos: o valor de toda constante de módulo em MAIÚSCULAS
#    (``ACCELERATION_METHODS``, ``TYPE_LABEL``...) — a chave fica de fora;
# 3. argumento de função que monta texto de tela (``FUNCOES_DE_TEXTO``);
# 4. módulo que é só regra e texto de tela (``MODULOS_DE_TEXTO``): todo literal.
#    O `gacrux_engine` entra aqui porque o motivo da recusa e montado em
#    listas (``problems.append``) e em subclasses de ``AppError``, que o item 1
#    não vê; o resto dos literais dele e argumento de linha de comando, sem
#    palavra da lista.
#
# Valem as mesmas exclusões de `src/ui` (docstring, log, chave, índice,
# comparação, SQL, cara de chave). Log fica como está: é ASCII de propósito.
SERVICOS = RAIZ / "src" / "services"
EXCECOES_DE_TELA = {"AppError", "ValueError", "PermissionError"}
FUNCOES_DE_TEXTO = {"add_alert": (0,)}
MODULOS_DE_TEXTO = {
    "src/services/certificates/gallery.py",
    "src/services/pairing/bye_policy.py",
    "src/services/pairing/gacrux_engine.py",
    "src/services/pairing/incidents.py",
    "src/services/pairing/gacrux_trf.py",
}


def _nome_da_chamada(chamada: ast.Call) -> str:
    return chamada.func.id if isinstance(chamada.func, ast.Name) else getattr(chamada.func, "attr", "")


def _nos_de_tela_do_servico(arvore: ast.Module, nome: str) -> set[int]:
    """``id()`` dos nós de `src/services` cujo texto vai para a tela."""
    escolhidos: set[int] = set()

    def pegar(no: ast.AST) -> None:
        escolhidos.update(id(filho) for filho in ast.walk(no))

    if nome in MODULOS_DE_TEXTO:
        pegar(arvore)
        return escolhidos
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        chamada = _nome_da_chamada(no)
        if chamada in EXCECOES_DE_TELA:
            for argumento in [*no.args, *(k.value for k in no.keywords)]:
                pegar(argumento)
        for indice in FUNCOES_DE_TEXTO.get(chamada, ()):
            if indice < len(no.args):
                pegar(no.args[indice])
    for no in arvore.body:
        alvos = no.targets if isinstance(no, ast.Assign) else [no.target] if isinstance(no, ast.AnnAssign) else []
        if no_valor := getattr(no, "value", None):
            if any(isinstance(alvo, ast.Name) and alvo.id.isupper() for alvo in alvos):
                pegar(no_valor)
    return escolhidos


def literais_de_servico_do_fonte(fonte: str, nome: str) -> list[tuple[str, str]]:
    """Os literais de UM arquivo de `src/services` que vão para a tela."""
    try:
        arvore = ast.parse(fonte)
    except SyntaxError:  # pragma: no cover - arquivo em edicao
        return []
    fora = _constantes_fora_da_tela(arvore)
    escolhidos = _nos_de_tela_do_servico(arvore, nome)
    return [
        (f"{nome}:{no.lineno}", no.value)
        for no in ast.walk(arvore)
        if isinstance(no, ast.Constant)
        and isinstance(no.value, str)
        and id(no) in escolhidos
        and id(no) not in fora
        and _parece_texto(no.value)
    ]


def literais_de_servico() -> list[tuple[str, str]]:
    """``(origem, texto)`` do texto de tela de `src/services` (ver o critério acima)."""
    achados: list[tuple[str, str]] = []
    for arquivo in sorted(SERVICOS.rglob("*.py")):
        nome = arquivo.relative_to(RAIZ).as_posix()
        achados.extend(literais_de_servico_do_fonte(arquivo.read_text(encoding="utf-8"), nome))
    return achados


# --- Texto semeado no banco ------------------------------------------------
#
# O banco nasce com níveis de aprendizagem e modelos de certificado escritos
# em `src/core/database.py` (`DEFAULT_LEARNING_LEVELS`,
# `DEFAULT_CERTIFICATE_TEMPLATES`...) e na galeria de modelos. Esse texto vai
# para a tela e para o certificado IMPRESSO, e passou anos sem acento
# ("Intermediario", "Certificado de Participacao") porque nenhuma das
# varreduras acima lia `src/core`. Vale o critério de `src/services`: o valor
# das constantes de módulo em MAIÚSCULAS (a chave fica de fora) e, na galeria,
# todo literal (ela é em ``MODULOS_DE_TEXTO``). Caminho de arquivo
# ("assets/.../xadrez_classico.png") cai na regra do literal técnico.
ARQUIVOS_DE_SEMENTE = ("src/core/database.py", "src/services/certificates/gallery.py")


def literais_de_semente() -> list[tuple[str, str]]:
    """``(origem, texto)`` do texto que o banco semeia (ver o critério acima)."""
    achados: list[tuple[str, str]] = []
    for nome in ARQUIVOS_DE_SEMENTE:
        achados.extend(literais_de_servico_do_fonte((RAIZ / nome).read_text(encoding="utf-8"), nome))
    return achados


def checar_lista_fechada(textos: list[tuple[str, str]] | None = None) -> list[str]:
    """Palavras da lista fechada escritas sem acento num texto de tela (RGS-27)."""
    if textos is None:
        # A galeria é nas duas leituras (serviço e semente): conta uma vez.
        textos = list(
            dict.fromkeys(
                _textos_do_catalogo() + literais_de_tela() + literais_de_servico() + literais_de_semente()
            )
        )
    problemas: list[str] = []
    for origem, texto in textos:
        visivel = _visivel(texto)
        for m in _PALAVRA_INTEIRA.finditer(visivel):
            palavra = m.group(0)
            if visivel[m.start() - 1 : m.start()] == "-" and palavra.lower() in _PRONOMES_ENCLITICOS:
                continue  # o "la" de "trocá-la" não é o advérbio "lá"
            certa = PALAVRAS_SEM_ACENTO.get(palavra.lower())
            if certa:
                problemas.append(f"{origem}: '{palavra}' sem acento — escreva '{certa}' (RGS-27).")
        for m in _VERBO_COM_PRONOME.finditer(visivel):
            certa = m.group(1) + _ACENTO_DO_INFINITIVO[m.group(2)] + "-" + m.group(3)
            problemas.append(f"{origem}: '{m.group(0)}' sem acento — escreva '{certa}' (RGS-27).")
    return problemas


def main() -> int:
    textos = corpus()
    if "--lista" in sys.argv:
        acentuadas = grafias_acentuadas(textos)
        suspeitas = sorted(
            {
                palavra
                for _origem, texto in textos
                for palavra in _PALAVRA.findall(_visivel(texto))
                if _sem_acento(palavra) == palavra
                and palavra.lower() in acentuadas
                and palavra.lower() not in HOMOGRAFOS
            }
        )
        for palavra in suspeitas:
            print(f"{palavra} -> {sorted(acentuadas[palavra.lower()])}")
        return 0

    problemas = checar_acentos() + checar_lista_fechada()
    if problemas:
        print("Acentuação de textos visíveis:\n")
        for problema in problemas:
            print(f"  {problema}")
        print(f"\n{len(problemas)} ocorrência(s).")
        return 1
    print(
        f"Acentuação OK ({len(textos)} textos visíveis conferidos; "
        f"lista fechada de {len(PALAVRAS_SEM_ACENTO)} palavras em todo literal de src/ui "
        f"e no texto de tela de src/services e das sementes do banco)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
