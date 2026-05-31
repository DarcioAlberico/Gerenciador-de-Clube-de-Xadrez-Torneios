# Especificação Técnica de Implementação - Módulo Pedagógico Avançado

**Projeto:** Gerenciador de Clube e Torneios de Xadrez  
**Módulo:** Estrutura pedagógica, base de exercícios, FEN/PGN, chessboard, geração de PDF e acompanhamento de progresso  
**Arquivo analisado:** `Texto colado.txt`  
**Data:** 26/05/2026  
**Versão deste documento:** 2.0 - especificação expandida para implementação

---

## 1. Resumo executivo

O arquivo original apresenta uma boa direção arquitetural: separar serviços de domínio, manter validação centralizada, reutilizar `SecurityService.require_permission()`, preservar `AppError` como mecanismo de erro de aplicação e integrar exercícios, níveis pedagógicos, listas de treino, FEN/PGN, tabuleiro e geração de PDF. Porém, para virar um módulo pronto para implementação, a proposta precisa sair do nível conceitual e definir contratos técnicos completos: tabelas, migrations, serviços, rotas, payloads, filas de processamento, fluxo de armazenamento, validação robusta de xadrez, versionamento de material, rastreamento pedagógico, testes e critérios de aceite.

A recomendação principal é implementar o módulo como uma extensão incremental dos serviços existentes (`exercises.py`, `learning.py`, `training.py`), sem reescrever o núcleo atual. O novo módulo deve ficar dividido em serviços especializados:

- `ChessValidationService`: valida FEN, PGN, lances e posições.
- `DiagramRenderService`: gera SVG/PNG de tabuleiros a partir de FEN.
- `PedagogicalMaterialService`: gerencia materiais pedagógicos e versões.
- `ExerciseAssetService`: gerencia PDFs, PGNs, imagens, diagramas e anexos ligados a exercícios.
- `PDFGenerationService`: gera folhas de exercícios, soluções, planos de aula e partidas comentadas em PDF.
- `PedagogyProgressService`: calcula progresso por aluno, categoria, nível e tema.
- `PedagogyRecommendationService`: sugere revisão espaçada e exercícios prioritários.
- `JobService`: controla tarefas assíncronas de PDF, importação de PGN e renderização pesada.

O ponto mais importante é tratar a geração de PDF e a renderização de diagramas como **tarefas rastreáveis**, não como chamadas síncronas simples. O usuário deve receber um `job_id`, acompanhar `queued/running/succeeded/failed`, e baixar o PDF quando estiver pronto. Isso evita travamento da interface, timeout HTTP e perda de rastreabilidade.

---

## 2. Premissas e limites da análise

Esta especificação foi produzida a partir do conteúdo do arquivo enviado, que menciona como base os módulos `exercises.py`, `learning.py` e `training.py`. Como o código-fonte completo desses módulos não foi enviado nesta conversa, as decisões abaixo assumem que o projeto já possui:

1. Uma classe ou camada `Database` usada pelos serviços atuais.
2. Um padrão de erro `AppError`.
3. Um serviço de segurança `SecurityService` com `require_permission()`.
4. Serviços de domínio semelhantes a `ExerciseService`, `LearningLevelService` e `TrainingService`.
5. Banco SQLite em ambiente inicial, com possibilidade futura de PostgreSQL.
6. Interface web ou desktop-web que possa consumir endpoints HTTP.

Quando a implementação real for feita, as assinaturas dos métodos de banco devem ser ajustadas ao estilo exato já usado no projeto. A especificação abaixo evita impor um framework único; ela funciona tanto com FastAPI quanto com Flask, embora FastAPI seja a opção mais indicada para contratos tipados e OpenAPI automático.

---

## 3. Diagnóstico técnico do arquivo original

### 3.1 Pontos fortes

O arquivo original já acerta em várias decisões estruturais:

| Área | Avaliação | Comentário técnico |
|---|---:|---|
| Separação por serviços | Forte | A proposta respeita o padrão `Service Layer`, evitando misturar regra de negócio, banco e interface. |
| Permissões | Forte | O uso de `SecurityService.require_permission()` mantém controle de acesso consistente. |
| Validação antes do banco | Forte | O padrão `_validated_payload()` reduz dados inválidos persistidos. |
| PDF como serviço dedicado | Correto | A geração de PDF não deve ficar dentro de `ExerciseService` ou `TrainingService`. |
| Uso de FEN/PGN | Correto | O domínio de xadrez precisa de validação própria; não deve depender apenas de campos de texto. |
| Expansão não intrusiva | Correto | O módulo deve evoluir sem quebrar os fluxos atuais. |

### 3.2 Lacunas críticas

A proposta original ainda está incompleta nos seguintes pontos:

| Lacuna | Risco | Correção recomendada |
|---|---|---|
| Ausência de fila/status para PDF | Timeout, interface travada, perda de erro | Criar `pdf_generation_jobs` e worker assíncrono. |
| Validação FEN simplificada | Aceitar posição ilegal ou diagnóstico ruim | Usar `python-chess` com `board.is_valid()`, `board.status()` e erro padronizado. |
| Validação PGN simplificada | PGN parcialmente inválido ser aceito | Verificar `game.errors`, múltiplos jogos e encoding. |
| Cálculo de material incorreto | Código não executa como está | Implementar tabela própria de valores de peças. |
| Sem versionamento de material | Perda de histórico e auditoria | Criar `pedagogical_material_versions`. |
| Sem tabela de arquivos genérica | Duplicação de path e metadados | Criar `asset_files` e relacionar com exercícios/materiais. |
| Sem política de storage | Colisão, path traversal, dificuldade de backup | Usar UUID/hash, diretórios por clube e tipo. |
| Sem contrato de erro API | Frontend sem tratamento previsível | Padronizar `ErrorResponse`. |
| Sem critérios de aceite | Dificulta validar entrega | Definir testes e comportamento esperado por fase. |
| Sem importação PGN robusta | Dificuldade para livros/treinos grandes | Criar fluxo de importação com job e relatório de erros. |

### 3.3 Correções técnicas específicas

#### 3.3.1 Não usar `pgn-reader` como dependência principal

O `python-chess` já fornece parsing de PGN com `chess.pgn.read_game()`, árvore de variações, comentários, NAGs e posições intermediárias. Para o módulo proposto, `pgn-reader` não é necessário na primeira versão. Menos dependências reduzem conflitos, simplificam instalação e facilitam testes.

#### 3.3.2 Corrigir cálculo de material

O trecho original sugere algo como `board.piece_type_score(p)`, mas esse método não faz parte do uso normal de `python-chess`. O correto é definir explicitamente os valores de peça:

```python
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}
```

Depois, somar material branco e preto a partir de `board.piece_map()`.

#### 3.3.3 Tratar PGN como parser permissivo

O parser de PGN do `python-chess` é útil e robusto, mas pode ser permissivo. A implementação deve verificar `game.errors` e decidir se aceita, rejeita ou aceita com aviso. Para uma plataforma pedagógica, recomenda-se:

- **Modo estrito** para materiais oficiais: rejeitar PGN com erros.
- **Modo flexível** para importação inicial: importar o que for possível e gerar relatório.
- **Modo editor**: mostrar erros por lance ao professor.

---

## 4. Objetivos funcionais do módulo

### 4.1 Para professores e administradores

1. Criar materiais pedagógicos por nível, categoria, tema e objetivo didático.
2. Criar folhas de exercícios em PDF com ou sem respostas.
3. Anexar PDFs, PGNs, diagramas e imagens a exercícios e materiais.
4. Validar FEN antes de salvar uma posição.
5. Importar PGNs e transformar partidas em exercícios, exemplos ou partidas comentadas.
6. Montar listas de treino por categoria: tática, finais, estratégia, abertura, cálculo, defesa e conversão de vantagem.
7. Gerar diagramas de alta qualidade a partir de FEN.
8. Versionar materiais para manter histórico de alterações.
9. Reutilizar exercícios em múltiplos materiais sem duplicar dados.
10. Acompanhar desempenho dos alunos por tema e nível.

### 4.2 Para alunos/enxadristas

1. Resolver exercícios com tabuleiro interativo.
2. Receber feedback imediato ou diferido, conforme configuração da lista.
3. Revisar exercícios errados por repetição espaçada.
4. Visualizar progresso por categoria, nível e tema.
5. Baixar material em PDF se permitido pelo clube.

### 4.3 Para o sistema

1. Manter integridade de FEN/PGN.
2. Evitar duplicação de arquivos e diagramas.
3. Gerar PDFs de forma assíncrona e rastreável.
4. Registrar auditoria de alterações importantes.
5. Manter compatibilidade com o banco atual.
6. Permitir migração futura para PostgreSQL e storage externo.

---

## 5. Requisitos não funcionais

| Requisito | Especificação |
|---|---|
| Performance | Validar FEN em menos de 100 ms; gerar diagrama SVG em menos de 500 ms para casos comuns; PDF via job. |
| Escalabilidade | Módulo deve funcionar em SQLite inicialmente, mas SQL deve ser compatível com PostgreSQL sempre que possível. |
| Segurança | Todo upload deve validar MIME, extensão, tamanho, path, permissão e isolamento por clube. |
| Auditabilidade | Criação, atualização, remoção e geração de PDF devem gravar logs ou registros de auditoria. |
| Manutenibilidade | Cada serviço deve ter responsabilidade única e testes unitários. |
| Portabilidade | Evitar dependências de sistema difíceis na primeira versão; documentar dependências como Cairo/Pango no caso do WeasyPrint. |
| Usabilidade | Frontend deve validar FEN/PGN em tempo real e explicar erros em português. |
| Robustez | Jobs devem ter status, tentativas, erro legível, traceback interno e possibilidade de reprocessamento. |
| Impressão | PDFs devem ter layout A4, margens previsíveis, cabeçalho do clube e opção com/sem soluções. |

---

## 6. Arquitetura proposta

### 6.1 Visão em camadas

```text
+------------------------------+
| Frontend Web                 |
| React/Vue + chessground      |
| Editor de FEN/PGN/PDF        |
+---------------+--------------+
                |
                v
+------------------------------+
| API HTTP                     |
| FastAPI/Flask routers        |
| Auth + permissions           |
+---------------+--------------+
                |
                v
+------------------------------+
| Service Layer                |
| ChessValidationService       |
| DiagramRenderService         |
| PedagogicalMaterialService   |
| ExerciseAssetService         |
| PDFGenerationService         |
| PedagogyProgressService      |
| JobService                   |
+---------------+--------------+
                |
      +---------+---------+
      |                   |
      v                   v
+-------------+     +----------------+
| Database    |     | Asset Storage  |
| SQLite/PG   |     | PDFs/SVG/PGN   |
+-------------+     +----------------+
      |
      v
+------------------------------+
| Worker assíncrono            |
| Celery/RQ/thread inicial     |
| PDF, importação, render      |
+------------------------------+
```

### 6.2 Regra de ouro da arquitetura

O backend de requisição não deve executar diretamente tarefas pesadas. Ele deve:

1. Validar payload.
2. Conferir permissão.
3. Criar registro de job.
4. Enfileirar tarefa.
5. Retornar `202 Accepted` com `job_id`.
6. Permitir consulta de progresso por endpoint.

### 6.3 Serviços novos

| Serviço | Responsabilidade | Depende de |
|---|---|---|
| `ChessValidationService` | Validar FEN, PGN, SAN/UCI, extrair posições e metadados. | `python-chess`, `AppError` |
| `DiagramRenderService` | Gerar e cachear SVG/PNG de tabuleiro. | `python-chess`, `chess.svg`, storage |
| `PedagogicalMaterialService` | CRUD de materiais e versões. | `Database`, `SecurityService` |
| `ExerciseAssetService` | Upload, vinculação e remoção de ativos. | storage, `Database` |
| `PDFGenerationService` | Renderizar HTML/Jinja2 e gerar PDF. | Jinja2, WeasyPrint, storage |
| `PGNImportService` | Importar PGNs grandes e mapear jogos/exercícios. | `python-chess`, jobs |
| `PedagogyProgressService` | Calcular desempenho por membro e categoria. | attempts, exercises |
| `PedagogyRecommendationService` | Definir revisões e sugestões. | stats, spaced repetition |
| `JobService` | Criar, atualizar e consultar jobs. | `Database`, worker |

---

## 7. Estrutura sugerida de pastas

```text
app/
  services/
    exercises.py
    learning.py
    training.py
    pedagogy.py
    chess_validation.py
    diagram_render.py
    exercise_assets.py
    pdf_generation.py
    pgn_import.py
    pedagogy_progress.py
    pedagogy_recommendation.py
    jobs.py
  repositories/
    pedagogy_repository.py
    asset_repository.py
    pdf_repository.py
    progress_repository.py
  api/
    routes_chess.py
    routes_pedagogy.py
    routes_assets.py
    routes_pdf.py
    routes_progress.py
  schemas/
    chess_schemas.py
    pedagogy_schemas.py
    asset_schemas.py
    pdf_schemas.py
    progress_schemas.py
  templates/
    pdf/
      base.html
      exercise_sheet.html
      solution_sheet.html
      lesson_plan.html
      annotated_game.html
  static/
    pdf_css/
      print.css
  workers/
    celery_app.py
    tasks_pdf.py
    tasks_pgn.py
  migrations/
    2026_05_26_pedagogy_module.sql
  tests/
    test_chess_validation.py
    test_pedagogy_materials.py
    test_pdf_generation.py
    test_pgn_import.py
    test_progress.py
storage/
  assets/
  diagrams/
  pdfs/
  imports/
```

---

## 8. Modelo de dados proposto

### 8.1 Princípios do modelo

1. **Não duplicar arquivo físico:** arquivo vai em `asset_files`; os vínculos ficam em tabelas relacionais.
2. **Não misturar material e PDF gerado:** material é entidade pedagógica; PDF é uma saída versionada.
3. **Versionar conteúdo textual importante:** materiais podem ter versões.
4. **Separar posição de xadrez de exercício:** a mesma FEN pode ser usada em vários exercícios.
5. **Guardar jobs:** tudo que pode demorar deve ser rastreável.
6. **Permitir analytics:** tentativas devem alimentar estatísticas agregadas e revisão espaçada.

### 8.2 Tabelas principais

#### 8.2.1 `pedagogical_materials`

```sql
CREATE TABLE IF NOT EXISTS pedagogical_materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id INTEGER NOT NULL,
    learning_level_id INTEGER,
    title TEXT NOT NULL,
    slug TEXT,
    material_type TEXT NOT NULL CHECK(material_type IN (
        'exercise_sheet',
        'lesson_plan',
        'strategy_guide',
        'annotated_game',
        'diagram_pack',
        'homework',
        'assessment'
    )),
    summary TEXT,
    objective TEXT,
    target_audience TEXT,
    estimated_minutes INTEGER,
    difficulty TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN (
        'draft', 'review', 'published', 'archived'
    )),
    visibility TEXT NOT NULL DEFAULT 'private' CHECK(visibility IN (
        'private', 'club', 'public'
    )),
    tags TEXT,
    created_by INTEGER,
    updated_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP
);
```

#### 8.2.2 `pedagogical_material_versions`

```sql
CREATE TABLE IF NOT EXISTS pedagogical_material_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    content_markdown TEXT,
    content_json TEXT,
    change_note TEXT,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(material_id) REFERENCES pedagogical_materials(id),
    UNIQUE(material_id, version_number)
);
```

#### 8.2.3 `pedagogical_material_items`

Relaciona material com exercícios, diagramas, jogos PGN ou blocos livres.

```sql
CREATE TABLE IF NOT EXISTS pedagogical_material_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL,
    item_type TEXT NOT NULL CHECK(item_type IN (
        'exercise', 'position', 'pgn_game', 'text_block', 'asset_file'
    )),
    item_id INTEGER,
    sort_order INTEGER NOT NULL DEFAULT 0,
    title TEXT,
    instructions TEXT,
    points INTEGER DEFAULT 0,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(material_id) REFERENCES pedagogical_materials(id)
);
```

#### 8.2.4 `asset_files`

```sql
CREATE TABLE IF NOT EXISTS asset_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id INTEGER NOT NULL,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_ext TEXT,
    mime_type TEXT,
    file_size_bytes INTEGER NOT NULL DEFAULT 0,
    sha256 TEXT,
    storage_backend TEXT NOT NULL DEFAULT 'local',
    asset_kind TEXT NOT NULL CHECK(asset_kind IN (
        'pdf', 'pgn', 'image', 'diagram_svg', 'diagram_png', 'template', 'other'
    )),
    uploaded_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sha256, club_id)
);
```

#### 8.2.5 `exercise_assets`

```sql
CREATE TABLE IF NOT EXISTS exercise_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_id INTEGER NOT NULL,
    asset_file_id INTEGER,
    asset_type TEXT NOT NULL CHECK(asset_type IN (
        'diagram', 'pgn', 'source_pdf', 'image', 'solution_pdf', 'audio', 'video'
    )),
    fen TEXT,
    pgn_game_id INTEGER,
    caption TEXT,
    sort_order INTEGER DEFAULT 0,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(exercise_id) REFERENCES exercises(id),
    FOREIGN KEY(asset_file_id) REFERENCES asset_files(id)
);
```

#### 8.2.6 `chess_positions`

```sql
CREATE TABLE IF NOT EXISTS chess_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fen TEXT NOT NULL,
    normalized_fen TEXT NOT NULL,
    side_to_move TEXT NOT NULL CHECK(side_to_move IN ('white', 'black')),
    fullmove_number INTEGER,
    halfmove_clock INTEGER,
    castling_rights TEXT,
    en_passant_square TEXT,
    material_balance_cp INTEGER DEFAULT 0,
    legal_moves_count INTEGER DEFAULT 0,
    is_check INTEGER DEFAULT 0,
    is_checkmate INTEGER DEFAULT 0,
    is_stalemate INTEGER DEFAULT 0,
    validation_status TEXT NOT NULL DEFAULT 'valid',
    validation_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(normalized_fen)
);
```

#### 8.2.7 `pgn_games`

```sql
CREATE TABLE IF NOT EXISTS pgn_games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id INTEGER NOT NULL,
    asset_file_id INTEGER,
    event TEXT,
    site TEXT,
    game_date TEXT,
    round TEXT,
    white_player TEXT,
    black_player TEXT,
    result TEXT,
    eco TEXT,
    initial_fen TEXT,
    final_fen TEXT,
    ply_count INTEGER DEFAULT 0,
    pgn_text TEXT NOT NULL,
    parse_status TEXT NOT NULL DEFAULT 'valid' CHECK(parse_status IN ('valid', 'warning', 'invalid')),
    parse_errors TEXT,
    imported_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(asset_file_id) REFERENCES asset_files(id)
);
```

#### 8.2.8 `pdf_generation_jobs`

```sql
CREATE TABLE IF NOT EXISTS pdf_generation_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id INTEGER NOT NULL,
    requested_by INTEGER,
    job_type TEXT NOT NULL CHECK(job_type IN (
        'training_list_pdf', 'material_pdf', 'lesson_plan_pdf', 'annotated_game_pdf'
    )),
    source_type TEXT NOT NULL CHECK(source_type IN (
        'training_list', 'material', 'session', 'pgn_game'
    )),
    source_id INTEGER NOT NULL,
    template_key TEXT NOT NULL,
    include_solutions INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN (
        'queued', 'running', 'succeeded', 'failed', 'cancelled'
    )),
    progress_percent INTEGER DEFAULT 0,
    current_step TEXT,
    error_message TEXT,
    internal_traceback TEXT,
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    finished_at TIMESTAMP
);
```

#### 8.2.9 `pdf_outputs`

```sql
CREATE TABLE IF NOT EXISTS pdf_outputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    club_id INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    source_id INTEGER NOT NULL,
    asset_file_id INTEGER NOT NULL,
    title TEXT,
    include_solutions INTEGER DEFAULT 0,
    page_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(job_id) REFERENCES pdf_generation_jobs(id),
    FOREIGN KEY(asset_file_id) REFERENCES asset_files(id)
);
```

#### 8.2.10 `spaced_repetition_reviews`

```sql
CREATE TABLE IF NOT EXISTS spaced_repetition_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    exercise_id INTEGER NOT NULL,
    category_key TEXT,
    easiness REAL DEFAULT 2.5,
    interval_days INTEGER DEFAULT 1,
    repetitions INTEGER DEFAULT 0,
    last_quality INTEGER,
    last_reviewed_at TIMESTAMP,
    next_review_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(member_id, exercise_id)
);
```

### 8.3 Índices recomendados

```sql
CREATE INDEX IF NOT EXISTS idx_materials_club_status
    ON pedagogical_materials(club_id, status);

CREATE INDEX IF NOT EXISTS idx_materials_level
    ON pedagogical_materials(learning_level_id);

CREATE INDEX IF NOT EXISTS idx_material_items_material_order
    ON pedagogical_material_items(material_id, sort_order);

CREATE INDEX IF NOT EXISTS idx_assets_club_kind
    ON asset_files(club_id, asset_kind);

CREATE INDEX IF NOT EXISTS idx_positions_normalized_fen
    ON chess_positions(normalized_fen);

CREATE INDEX IF NOT EXISTS idx_pdf_jobs_status
    ON pdf_generation_jobs(status, created_at);

CREATE INDEX IF NOT EXISTS idx_reviews_member_next
    ON spaced_repetition_reviews(member_id, next_review_at);
```

---

## 9. Taxonomia pedagógica

A taxonomia deve ser flexível. O arquivo original já sugere categorias estratégicas, mas elas precisam de granularidade suficiente para treinos reais.

### 9.1 Categorias principais

```python
PEDAGOGY_CATEGORIES = {
    "tactics": "Tática",
    "calculation": "Cálculo",
    "positional": "Jogo posicional",
    "opening": "Abertura",
    "middlegame": "Meio-jogo",
    "endgame": "Final",
    "defense": "Defesa",
    "attack": "Ataque",
    "strategy": "Estratégia",
    "game_analysis": "Análise de partidas",
}
```

### 9.2 Subcategorias úteis para xadrez

```python
PEDAGOGY_SUBCATEGORIES = {
    "tactics.fork": "Garfo",
    "tactics.pin": "Cravada",
    "tactics.skewer": "Raio X / espeto",
    "tactics.discovery": "Ataque descoberto",
    "tactics.deflection": "Desvio",
    "tactics.decoy": "Atração",
    "tactics.overload": "Sobrecarga",
    "tactics.back_rank": "Mate na última fileira",
    "calculation.candidate_moves": "Lances candidatos",
    "calculation.forcing_moves": "Lances forçados",
    "positional.weak_squares": "Casas fracas",
    "positional.outpost": "Posto avançado",
    "positional.open_file": "Coluna aberta",
    "endgame.king_pawn": "Finais de rei e peão",
    "endgame.rook": "Finais de torre",
    "endgame.minor_pieces": "Finais de peças menores",
    "opening.principles": "Princípios de abertura",
    "middlegame.plan": "Plano de meio-jogo",
}
```

### 9.3 Níveis de progressão

```python
PROGRESSION_LEVELS = {
    "discovery": "Descoberta",
    "guided": "Guiado",
    "independent": "Autônomo",
    "mastery": "Domínio",
}
```

### 9.4 Nível didático recomendado

Além de `difficulty`, convém ter `pedagogical_stage`, porque um exercício pode ser taticamente fácil mas didaticamente avançado se exige plano estratégico.

| Campo | Exemplo | Uso |
|---|---|---|
| `difficulty` | `easy`, `medium`, `hard` | Dificuldade de resolução. |
| `pedagogical_stage` | `guided` | Grau de autonomia esperado. |
| `category_key` | `endgame` | Macrotema. |
| `subcategory_key` | `endgame.rook` | Tema específico. |
| `estimated_minutes` | `8` | Tempo previsto. |
| `solution_depth` | `3` | Número de lances da linha principal. |

---

## 10. Validação de FEN e PGN

### 10.1 Dependências recomendadas

```bash
pip install python-chess
```

`python-chess` é suficiente para:

- Validar FEN.
- Gerar movimentos legais.
- Ler PGN.
- Percorrer linha principal.
- Ler comentários e NAGs.
- Gerar SVG de tabuleiro.

### 10.2 Serviço `ChessValidationService`

```python
# app/services/chess_validation.py
from __future__ import annotations

import io
import json
from dataclasses import dataclass
from typing import Any

import chess
import chess.pgn

from app.security import AppError

PIECE_VALUES_CP = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}


@dataclass(frozen=True)
class FenValidationResult:
    valid: bool
    fen: str
    normalized_fen: str
    side_to_move: str
    legal_moves_count: int
    material_balance_cp: int
    is_check: bool
    is_checkmate: bool
    is_stalemate: bool
    status_code: int
    message: str


class ChessValidationService:
    @staticmethod
    def validate_fen(fen: str) -> dict[str, Any]:
        fen = (fen or "").strip()
        if not fen:
            raise AppError("Informe uma FEN.")

        try:
            board = chess.Board(fen)
        except ValueError as exc:
            raise AppError("FEN mal formatada.") from exc

        status_code = int(board.status())
        if not board.is_valid():
            raise AppError(f"FEN inválida ou posição ilegal. Status: {status_code}")

        white_material = 0
        black_material = 0
        for piece in board.piece_map().values():
            value = PIECE_VALUES_CP[piece.piece_type]
            if piece.color == chess.WHITE:
                white_material += value
            else:
                black_material += value

        return {
            "valid": True,
            "fen": fen,
            "normalized_fen": board.fen(),
            "side_to_move": "white" if board.turn == chess.WHITE else "black",
            "legal_moves_count": sum(1 for _ in board.legal_moves),
            "material_balance_cp": white_material - black_material,
            "is_check": board.is_check(),
            "is_checkmate": board.is_checkmate(),
            "is_stalemate": board.is_stalemate(),
            "status_code": status_code,
            "message": "FEN válida.",
        }

    @staticmethod
    def parse_pgn(pgn_text: str, strict: bool = True) -> dict[str, Any]:
        pgn_text = (pgn_text or "").strip()
        if not pgn_text:
            raise AppError("Informe um PGN.")

        handle = io.StringIO(pgn_text)
        games: list[dict[str, Any]] = []
        index = 0

        while True:
            game = chess.pgn.read_game(handle)
            if game is None:
                break

            index += 1
            errors = [str(error) for error in getattr(game, "errors", [])]
            if strict and errors:
                raise AppError(f"PGN contém erros no jogo {index}: {errors[0]}")

            board = game.board()
            moves = []
            positions = [board.fen()]

            for move_number, move in enumerate(game.mainline_moves(), start=1):
                san = board.san(move)
                uci = move.uci()
                board.push(move)
                moves.append({
                    "ply": move_number,
                    "san": san,
                    "uci": uci,
                    "fen_after": board.fen(),
                })
                positions.append(board.fen())

            games.append({
                "headers": dict(game.headers),
                "moves": moves,
                "initial_fen": game.board().fen(),
                "final_fen": board.fen(),
                "ply_count": len(moves),
                "result": game.headers.get("Result", "*"),
                "errors": errors,
                "parse_status": "warning" if errors else "valid",
            })

        if not games:
            raise AppError("PGN vazio ou mal formatado.")

        return {
            "valid": all(not game["errors"] for game in games),
            "game_count": len(games),
            "games": games,
        }
```

### 10.3 Regras de validação de FEN

| Regra | Comportamento |
|---|---|
| Campo vazio | Rejeitar com `AppError("Informe uma FEN.")`. |
| FEN mal formatada | Rejeitar com `AppError("FEN mal formatada.")`. |
| Reis ausentes ou múltiplos reis | Rejeitar como posição ilegal. |
| Peões na primeira/oitava fila | Rejeitar como posição ilegal. |
| Rei em xeque por posição impossível | Rejeitar quando `board.is_valid()` retornar falso. |
| FEN válida | Retornar FEN normalizada, lado a mover, quantidade de lances legais e status. |

### 10.4 Regras de validação de PGN

| Cenário | Modo estrito | Modo flexível |
|---|---|---|
| PGN vazio | Rejeita | Rejeita |
| Lance ilegal | Rejeita | Importa com aviso se houver jogo parcial recuperável |
| Cabeçalhos ausentes | Aceita com valores padrão | Aceita |
| Múltiplos jogos | Aceita e retorna lista | Aceita e retorna lista |
| Comentários e NAGs | Preserva | Preserva |
| Encoding com BOM | Abrir arquivo com `utf-8-sig` na importação | Idem |

---

## 11. Renderização de diagramas

### 11.1 Objetivo

Gerar diagramas consistentes para:

- Visualização no frontend.
- Folhas de exercícios em PDF.
- Materiais pedagógicos.
- Pacotes de diagramas.

### 11.2 Serviço `DiagramRenderService`

```python
# app/services/diagram_render.py
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

import chess
import chess.svg

from app.security import AppError
from app.services.chess_validation import ChessValidationService


class DiagramRenderService:
    def __init__(self, storage_dir: str = "storage/diagrams") -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def render_svg(
        self,
        fen: str,
        *,
        size: int = 360,
        coordinates: bool = True,
        flipped: bool = False,
        arrows: Iterable[tuple[str, str]] | None = None,
        squares: Iterable[str] | None = None,
    ) -> dict[str, str]:
        ChessValidationService.validate_fen(fen)
        board = chess.Board(fen)

        selected_squares = None
        if squares:
            selected_squares = chess.SquareSet(chess.parse_square(s) for s in squares)

        svg_arrows = []
        if arrows:
            for source, target in arrows:
                svg_arrows.append(chess.svg.Arrow(
                    chess.parse_square(source),
                    chess.parse_square(target),
                ))

        cache_key = self._cache_key(fen, size, coordinates, flipped, arrows, squares)
        file_path = self.storage_dir / f"{cache_key}.svg"

        if not file_path.exists():
            svg = chess.svg.board(
                board=board,
                size=size,
                coordinates=coordinates,
                flipped=flipped,
                squares=selected_squares,
                arrows=svg_arrows,
            )
            file_path.write_text(svg, encoding="utf-8")

        return {
            "file_path": str(file_path),
            "cache_key": cache_key,
            "url": f"/storage/diagrams/{file_path.name}",
        }

    @staticmethod
    def _cache_key(*parts: object) -> str:
        raw = repr(parts).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:32]
```

### 11.3 Política de cache de diagramas

| Item | Recomendação |
|---|---|
| Chave | Hash de FEN + tamanho + orientação + setas + casas destacadas. |
| Formato primário | SVG. |
| Formato secundário | PNG para compatibilidade em PDF, se necessário. |
| Local | `storage/diagrams/{hash}.svg`. |
| Regeneração | Se arquivo existe, reaproveitar. |
| Limpeza | Job mensal pode remover diagramas não referenciados. |

---

## 12. Geração de PDF

### 12.1 Decisão de stack

A stack recomendada é:

```bash
pip install jinja2 weasyprint
```

**Jinja2** deve montar o HTML.  
**WeasyPrint** deve converter HTML/CSS para PDF.  
**python-chess** deve gerar os diagramas em SVG.

ReportLab é uma alternativa válida, mas para folhas pedagógicas com cabeçalhos, rodapés, listas, diagramas, estilos e variações de layout, HTML/CSS tende a ser mais produtivo e fácil de manter.

### 12.2 Fluxo técnico

```text
Usuário clica "Gerar PDF"
        |
        v
API valida permissão e payload
        |
        v
Cria pdf_generation_jobs(status='queued')
        |
        v
Worker busca job
        |
        v
Carrega fonte: training_list/material/pgn_game
        |
        v
Renderiza diagramas SVG
        |
        v
Renderiza HTML com Jinja2
        |
        v
Converte HTML para PDF
        |
        v
Salva arquivo em asset_files
        |
        v
Cria pdf_outputs
        |
        v
Marca job como succeeded
```

### 12.3 Templates previstos

| Template | Arquivo | Uso |
|---|---|---|
| Base | `base.html` | Layout comum, CSS, cabeçalho e rodapé. |
| Folha de exercícios | `exercise_sheet.html` | PDF sem soluções. |
| Gabarito | `solution_sheet.html` | PDF com respostas e comentários. |
| Plano de aula | `lesson_plan.html` | Material do professor. |
| Partida comentada | `annotated_game.html` | PGN formatado com diagramas. |

### 12.4 Exemplo de template Jinja2

```html
<!-- templates/pdf/exercise_sheet.html -->
{% extends "base.html" %}

{% block content %}
<section class="sheet-header">
  <h1>{{ title }}</h1>
  <p class="meta">
    Nível: {{ level_name }} | Categoria: {{ category_name }} | Tempo: {{ estimated_minutes }} min
  </p>
</section>

{% for item in exercises %}
<article class="exercise-card">
  <h2>Exercício {{ loop.index }}</h2>
  <p>{{ item.prompt }}</p>

  {% if item.diagram_svg %}
  <div class="diagram">
    {{ item.diagram_svg | safe }}
  </div>
  {% endif %}

  {% if include_solutions %}
  <section class="solution">
    <h3>Solução</h3>
    <p>{{ item.solution_text }}</p>
    {% if item.solution_pgn %}
    <pre>{{ item.solution_pgn }}</pre>
    {% endif %}
  </section>
  {% else %}
  <div class="answer-lines"></div>
  {% endif %}
</article>
{% endfor %}
{% endblock %}
```

### 12.5 CSS de impressão

```css
@page {
  size: A4;
  margin: 18mm 14mm 18mm 14mm;

  @bottom-center {
    content: "Página " counter(page) " de " counter(pages);
    font-size: 9pt;
    color: #666;
  }
}

body {
  font-family: "DejaVu Sans", Arial, sans-serif;
  font-size: 10.5pt;
  line-height: 1.45;
  color: #1d1d1d;
}

h1, h2, h3 {
  page-break-after: avoid;
}

.exercise-card {
  page-break-inside: avoid;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 14px;
}

.diagram {
  text-align: center;
  margin: 10px auto;
}

.diagram svg {
  width: 260px;
  height: 260px;
}

.answer-lines {
  height: 80px;
  border-bottom: 1px dashed #999;
  margin-top: 10px;
}

.solution {
  background: #f6f6f6;
  border-left: 4px solid #333;
  padding: 8px 12px;
}
```

### 12.6 Serviço `PDFGenerationService`

```python
# app/services/pdf_generation.py
from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from app.database import Database
from app.security import AppError, SecurityService
from app.services.diagram_render import DiagramRenderService


class PDFGenerationService:
    def __init__(
        self,
        db: Database,
        template_dir: str = "app/templates/pdf",
        output_dir: str = "storage/pdfs",
    ) -> None:
        self.db = db
        self.template_dir = template_dir
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(["html", "xml"]),
        )
        self.diagram_service = DiagramRenderService()

    def request_training_list_pdf(
        self,
        *,
        list_id: int,
        include_solutions: bool,
        requested_by: int,
        club_id: int,
    ) -> int:
        SecurityService(self.db).require_permission("pedagogy.pdf.generate")

        training_list = self.db.get_training_list(list_id)
        if not training_list:
            raise AppError("Lista de treino não encontrada.")

        return self.db.create_pdf_generation_job(
            club_id=club_id,
            requested_by=requested_by,
            job_type="training_list_pdf",
            source_type="training_list",
            source_id=list_id,
            template_key="exercise_sheet",
            include_solutions=1 if include_solutions else 0,
        )

    def run_job(self, job_id: int) -> str:
        job = self.db.get_pdf_generation_job(job_id)
        if not job:
            raise AppError("Job de PDF não encontrado.")

        try:
            self.db.update_pdf_job(job_id, status="running", progress_percent=5,
                                   current_step="Carregando dados")

            context = self._build_context(job)

            self.db.update_pdf_job(job_id, progress_percent=35,
                                   current_step="Renderizando HTML")
            template = self.env.get_template(f"{job['template_key']}.html")
            html = template.render(**context)

            self.db.update_pdf_job(job_id, progress_percent=65,
                                   current_step="Convertendo HTML em PDF")
            output_path = self.output_dir / f"job_{job_id}.pdf"
            HTML(string=html, base_url=".").write_pdf(str(output_path))

            self.db.update_pdf_job(job_id, progress_percent=85,
                                   current_step="Registrando arquivo")
            asset_file_id = self.db.create_asset_file_from_path(
                club_id=job["club_id"],
                path=str(output_path),
                original_filename=output_path.name,
                asset_kind="pdf",
            )
            self.db.create_pdf_output(
                job_id=job_id,
                club_id=job["club_id"],
                source_type=job["source_type"],
                source_id=job["source_id"],
                asset_file_id=asset_file_id,
                include_solutions=job["include_solutions"],
            )
            self.db.update_pdf_job(job_id, status="succeeded", progress_percent=100,
                                   current_step="Concluído")
            return str(output_path)

        except Exception as exc:
            self.db.update_pdf_job(
                job_id,
                status="failed",
                error_message=str(exc),
                internal_traceback=traceback.format_exc(),
            )
            raise

    def _build_context(self, job: dict[str, Any]) -> dict[str, Any]:
        if job["source_type"] == "training_list":
            return self._build_training_list_context(job)
        if job["source_type"] == "material":
            return self._build_material_context(job)
        raise AppError("Tipo de origem de PDF não suportado.")
```

### 12.7 Quando usar FastAPI `BackgroundTasks`, Celery ou RQ

| Opção | Uso recomendado |
|---|---|
| `BackgroundTasks` do FastAPI | Tarefas pequenas, rápidas e não críticas. Ex.: log simples, e-mail simples. |
| RQ + Redis | Fila simples para PDF/importação com baixa complexidade operacional. |
| Celery + Redis/RabbitMQ | Tarefas robustas, retries, múltiplos workers, monitoramento e escala. |
| Thread local inicial | Apenas MVP local; não recomendado para produção com múltiplos processos. |

Para este módulo, a recomendação é:

1. MVP: implementar `pdf_generation_jobs` e executor simples.
2. Produção pequena: migrar executor para RQ.
3. Produção maior: Celery com retries, filas separadas e monitoramento.

---

## 13. Gerenciamento de materiais pedagógicos

### 13.1 Tipos de material

```python
MATERIAL_TYPES = {
    "exercise_sheet": "Folha de exercícios",
    "lesson_plan": "Plano de aula",
    "strategy_guide": "Guia de estratégia",
    "annotated_game": "Partida comentada",
    "diagram_pack": "Pacote de diagramas",
    "homework": "Tarefa de casa",
    "assessment": "Avaliação",
}
```

### 13.2 Serviço `PedagogicalMaterialService`

```python
# app/services/pedagogy.py
from __future__ import annotations

import logging
from typing import Any

from app.database import Database
from app.security import AppError, SecurityService

logger = logging.getLogger(__name__)

MATERIAL_TYPES = {
    "exercise_sheet": "Folha de exercícios",
    "lesson_plan": "Plano de aula",
    "strategy_guide": "Guia de estratégia",
    "annotated_game": "Partida comentada",
    "diagram_pack": "Pacote de diagramas",
    "homework": "Tarefa de casa",
    "assessment": "Avaliação",
}

MATERIAL_STATUSES = {"draft", "review", "published", "archived"}
MATERIAL_VISIBILITIES = {"private", "club", "public"}


class PedagogicalMaterialService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.security = SecurityService(db)

    def create_material(self, data: dict[str, Any], *, user_id: int) -> int:
        self.security.require_permission("pedagogy.materials.manage")
        payload = self._validated_payload(data)
        payload["created_by"] = user_id
        payload["updated_by"] = user_id

        material_id = self.db.create_pedagogical_material(**payload)
        self.db.create_pedagogical_material_version(
            material_id=material_id,
            version_number=1,
            title=payload["title"],
            content_markdown=str(data.get("content_markdown", "")),
            content_json=str(data.get("content_json", "")),
            change_note="Versão inicial",
            created_by=user_id,
        )
        logger.info("Material pedagógico criado: %s", material_id)
        return material_id

    def update_material(self, material_id: int, data: dict[str, Any], *, user_id: int) -> int:
        self.security.require_permission("pedagogy.materials.manage")
        current = self.db.get_pedagogical_material(material_id)
        if not current:
            raise AppError("Material pedagógico não encontrado.")

        payload = self._validated_payload(data, partial=True)
        payload["updated_by"] = user_id
        self.db.update_pedagogical_material(material_id, **payload)

        if "content_markdown" in data or "content_json" in data:
            next_version = self.db.get_next_material_version_number(material_id)
            self.db.create_pedagogical_material_version(
                material_id=material_id,
                version_number=next_version,
                title=payload.get("title", current["title"]),
                content_markdown=str(data.get("content_markdown", "")),
                content_json=str(data.get("content_json", "")),
                change_note=str(data.get("change_note", "Atualização")),
                created_by=user_id,
            )

        logger.info("Material pedagógico atualizado: %s", material_id)
        return material_id

    @staticmethod
    def _validated_payload(data: dict[str, Any], partial: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {}

        if not partial or "title" in data:
            title = str(data.get("title", "")).strip()
            if not title:
                raise AppError("Informe o título do material.")
            payload["title"] = title

        if not partial or "material_type" in data:
            material_type = str(data.get("material_type", "")).strip()
            if material_type not in MATERIAL_TYPES:
                raise AppError("Tipo de material inválido.")
            payload["material_type"] = material_type

        if "status" in data:
            status = str(data.get("status", "draft")).strip()
            if status not in MATERIAL_STATUSES:
                raise AppError("Status de material inválido.")
            payload["status"] = status

        if "visibility" in data:
            visibility = str(data.get("visibility", "private")).strip()
            if visibility not in MATERIAL_VISIBILITIES:
                raise AppError("Visibilidade inválida.")
            payload["visibility"] = visibility

        optional_fields = [
            "club_id", "learning_level_id", "summary", "objective",
            "target_audience", "estimated_minutes", "difficulty", "tags",
        ]
        for field in optional_fields:
            if field in data:
                payload[field] = data.get(field)

        return payload
```

---

## 14. Uploads e armazenamento de ativos

### 14.1 Tipos aceitos

| Tipo | Extensões | MIME esperado | Limite inicial |
|---|---|---|---:|
| PDF | `.pdf` | `application/pdf` | 25 MB |
| PGN | `.pgn`, `.txt` | `text/plain`, `application/x-chess-pgn` | 10 MB |
| Imagem | `.png`, `.jpg`, `.jpeg`, `.webp`, `.svg` | `image/*` | 10 MB |
| Template | `.html`, `.css` | `text/html`, `text/css` | 2 MB |

### 14.2 Política de path seguro

Nunca salvar arquivo com o nome original diretamente. Usar:

```text
storage/assets/{club_id}/{asset_kind}/{yyyy}/{mm}/{uuid4}.{ext}
```

Exemplo:

```text
storage/assets/1/pgn/2026/05/9f1c2b8d1c9d4fbab92f.pgn
```

### 14.3 Validação mínima de upload

```python
ALLOWED_EXTENSIONS = {
    "pdf": {".pdf"},
    "pgn": {".pgn", ".txt"},
    "image": {".png", ".jpg", ".jpeg", ".webp", ".svg"},
}

MAX_UPLOAD_BYTES = {
    "pdf": 25 * 1024 * 1024,
    "pgn": 10 * 1024 * 1024,
    "image": 10 * 1024 * 1024,
}
```

Regras:

1. Conferir permissão `pedagogy.assets.upload`.
2. Conferir clube do usuário.
3. Sanitizar nome original apenas para exibição.
4. Gerar nome físico próprio.
5. Calcular SHA-256.
6. Validar extensão e MIME.
7. Persistir em `asset_files`.
8. Vincular a exercício/material se solicitado.

---

## 15. Contratos de API

### 15.1 Modelo de erro padrão

```json
{
  "error": {
    "code": "FEN_INVALID",
    "message": "FEN inválida ou posição ilegal.",
    "details": {
      "status_code": 2
    }
  }
}
```

### 15.2 `POST /api/v1/chess/validate-fen`

Request:

```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
}
```

Response `200`:

```json
{
  "valid": true,
  "normalized_fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
  "side_to_move": "black",
  "legal_moves_count": 20,
  "material_balance_cp": 0,
  "is_check": false,
  "is_checkmate": false,
  "is_stalemate": false
}
```

### 15.3 `POST /api/v1/chess/validate-pgn`

Request:

```json
{
  "pgn": "[Event \"Exemplo\"]\n[Result \"*\"]\n\n1. e4 e5 2. Nf3 Nc6 *",
  "strict": true
}
```

Response `200`:

```json
{
  "valid": true,
  "game_count": 1,
  "games": [
    {
      "headers": {
        "Event": "Exemplo",
        "Result": "*"
      },
      "ply_count": 4,
      "initial_fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
      "final_fen": "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
      "errors": []
    }
  ]
}
```

### 15.4 `POST /api/v1/chess/render-diagram`

Request:

```json
{
  "fen": "8/8/8/8/8/8/4K3/4k3 w - - 0 1",
  "size": 360,
  "coordinates": true,
  "flipped": false,
  "highlights": ["e2", "e1"],
  "arrows": [{"from": "e2", "to": "e1"}]
}
```

Response `200`:

```json
{
  "format": "svg",
  "image_url": "/storage/diagrams/1d8f0b2b6b6d42b1.svg",
  "cache_key": "1d8f0b2b6b6d42b1"
}
```

### 15.5 `POST /api/v1/pedagogy/materials`

Request:

```json
{
  "club_id": 1,
  "learning_level_id": 3,
  "title": "Finais básicos de rei e peão",
  "material_type": "lesson_plan",
  "summary": "Aula introdutória sobre oposição e quadrado do peão.",
  "objective": "Ensinar oposição, regra do quadrado e conversão de peão passado.",
  "target_audience": "Alunos iniciantes/intermediários",
  "estimated_minutes": 60,
  "difficulty": "easy",
  "visibility": "club",
  "tags": "finais, rei e peao, oposição",
  "content_markdown": "# Aula\n..."
}
```

Response `201`:

```json
{
  "id": 42,
  "status": "draft",
  "version_number": 1
}
```

### 15.6 `POST /api/v1/pedagogy/pdf-jobs`

Request:

```json
{
  "source_type": "training_list",
  "source_id": 12,
  "template_key": "exercise_sheet",
  "include_solutions": false
}
```

Response `202`:

```json
{
  "job_id": 301,
  "status": "queued",
  "poll_url": "/api/v1/pedagogy/pdf-jobs/301"
}
```

### 15.7 `GET /api/v1/pedagogy/pdf-jobs/{job_id}`

Response enquanto executa:

```json
{
  "job_id": 301,
  "status": "running",
  "progress_percent": 65,
  "current_step": "Convertendo HTML em PDF"
}
```

Response concluído:

```json
{
  "job_id": 301,
  "status": "succeeded",
  "progress_percent": 100,
  "download_url": "/api/v1/pedagogy/pdf-outputs/88/download"
}
```

### 15.8 `GET /api/v1/pedagogy/progress`

Query:

```text
/api/v1/pedagogy/progress?member_id=42&level_id=3
```

Response:

```json
{
  "member_id": 42,
  "level_id": 3,
  "correct_rate": 0.78,
  "avg_time_seconds": 45,
  "category_breakdown": [
    {"category": "tactics", "correct_rate": 0.82, "attempts": 50},
    {"category": "endgame", "correct_rate": 0.61, "attempts": 18}
  ],
  "recommended_exercises": [12, 45, 89]
}
```

---

## 16. Integração com o frontend e chessboard

### 16.1 Bibliotecas recomendadas

| Função | Opção recomendada | Observação |
|---|---|---|
| Regras de xadrez no frontend | `chess.js` | Validação rápida, SAN, FEN. |
| Renderização de tabuleiro | `chessground` | Robusto e usado em ambientes modernos de xadrez. |
| Alternativa simples | `chessboardjs` | Mais simples, mas menos flexível. |
| Editor PGN | componente próprio + parser backend | Backend continua fonte de verdade. |

### 16.2 Componentes principais

```text
PedagogyMaterialList
PedagogyMaterialEditor
ExerciseEditor
FenInput
PgnImportWizard
InteractiveChessboard
DiagramPreview
PDFGenerationPanel
PDFJobStatusBadge
ProgressDashboard
ReviewQueueView
```

### 16.3 Fluxo de criação de exercício com FEN

```text
Professor abre ExerciseEditor
        |
        v
Digita/cola FEN
        |
        v
Frontend valida sintaxe básica com chess.js
        |
        v
Backend valida com /chess/validate-fen
        |
        v
Se válido: renderiza preview com /chess/render-diagram
        |
        v
Professor define pergunta, resposta e categoria
        |
        v
Salva exercício
```

### 16.4 Fluxo de importação de PGN

```text
Professor envia arquivo PGN
        |
        v
API cria asset_file + pgn_import_job
        |
        v
Worker lê jogos com python-chess
        |
        v
Sistema mostra jogos encontrados e erros
        |
        v
Professor escolhe: criar partida comentada, exercícios ou material
```

### 16.5 Regras de UX

1. Todo erro de FEN/PGN deve ser mostrado em português.
2. Tabuleiro deve permitir orientação branca/preta.
3. Campo FEN deve ter botão "copiar FEN" e "posição inicial".
4. Campo PGN deve ter validação com resumo: jogos, lances, erros.
5. Geração de PDF deve mostrar status e não bloquear a tela.
6. O botão de download só aparece quando o job estiver `succeeded`.
7. Se PDF falhar, mostrar mensagem amigável e botão "tentar novamente".

---

## 17. Rastreamento pedagógico e repetição espaçada

### 17.1 Extensão de tentativas

Se já existir `record_attempt`, ele deve ser estendido para gravar:

| Campo | Descrição |
|---|---|
| `member_id` | Aluno. |
| `exercise_id` | Exercício resolvido. |
| `training_list_id` | Lista em que foi resolvido. |
| `answer_text` | Resposta digitada, se houver. |
| `selected_move_uci` | Lance escolhido no tabuleiro, se houver. |
| `is_correct` | Resultado. |
| `time_spent_seconds` | Tempo de resolução. |
| `hints_used` | Quantidade de dicas. |
| `attempt_number` | Tentativa do aluno naquele exercício. |
| `category_key` | Categoria do exercício. |
| `subcategory_key` | Subcategoria. |
| `difficulty` | Dificuldade. |

### 17.2 Métricas úteis

| Métrica | Fórmula inicial |
|---|---|
| Taxa de acerto | acertos / tentativas |
| Tempo médio | média de `time_spent_seconds` |
| Taxa de acerto ponderada | acerto com penalidade por dica e tempo excessivo |
| Tema fraco | categoria com baixa taxa e número mínimo de tentativas |
| Domínio | taxa >= 85% e revisão recente |
| Necessita revisão | erro recente ou intervalo vencido |

### 17.3 Algoritmo simples de revisão espaçada

Para MVP, não precisa implementar SM-2 completo. Um algoritmo simples é suficiente:

```python
def update_review_state(current, *, is_correct: bool, quality: int):
    # quality: 0..5, onde 5 = resposta correta sem esforço
    easiness = current.easiness or 2.5
    repetitions = current.repetitions or 0

    if not is_correct or quality < 3:
        repetitions = 0
        interval_days = 1
    else:
        repetitions += 1
        if repetitions == 1:
            interval_days = 1
        elif repetitions == 2:
            interval_days = 3
        else:
            interval_days = round((current.interval_days or 3) * easiness)

    easiness = max(1.3, easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
    return repetitions, interval_days, easiness
```

### 17.4 Recomendação de exercícios

Prioridade sugerida:

```text
score =
  + 50 se revisão vencida
  + 30 se errou recentemente
  + 20 se categoria está abaixo de 70%
  + 10 se exercício pertence ao nível atual
  - 10 se acertou 3 vezes seguidas
```

---

## 18. Segurança e permissões

### 18.1 Permissões novas

```python
PEDAGOGY_PERMISSIONS = {
    "pedagogy.materials.read": "Visualizar materiais pedagógicos",
    "pedagogy.materials.manage": "Criar e editar materiais pedagógicos",
    "pedagogy.materials.publish": "Publicar materiais pedagógicos",
    "pedagogy.assets.upload": "Enviar arquivos pedagógicos",
    "pedagogy.assets.delete": "Excluir arquivos pedagógicos",
    "pedagogy.pdf.generate": "Gerar PDFs pedagógicos",
    "pedagogy.analytics.view": "Visualizar progresso pedagógico",
    "pedagogy.recommendations.view": "Visualizar recomendações de estudo",
    "chess.position.validate": "Validar posições de xadrez",
}
```

### 18.2 Regras obrigatórias

1. Todo material pertence a um `club_id`.
2. Usuário só acessa material do próprio clube, salvo permissão global.
3. Arquivos nunca são servidos por path direto sem checagem de permissão quando forem privados.
4. Upload deve bloquear path traversal: `../`, `\`, nomes absolutos etc.
5. HTML usado em PDF deve escapar conteúdo de usuário por padrão.
6. Apenas campos explicitamente confiáveis podem usar `|safe` no Jinja2.
7. PGN e comentários não devem ser executados nem transformados em HTML sem sanitização.
8. PDF gerado deve ser registrado em `asset_files` e vinculado ao job.
9. Falhas internas devem registrar traceback no banco/log, mas retornar mensagem curta ao frontend.
10. Materiais publicados devem ser imutáveis; edição cria nova versão.

---

## 19. Migrations e compatibilidade

### 19.1 Estratégia incremental

1. Criar tabelas novas sem alterar tabelas existentes.
2. Adicionar colunas opcionais em `exercises`, se necessário.
3. Popular permissões novas.
4. Criar índices.
5. Implementar serviços usando métodos novos em `Database`.
6. Integrar UI gradualmente.

### 19.2 Possíveis colunas novas em `exercises`

```sql
ALTER TABLE exercises ADD COLUMN category_key TEXT;
ALTER TABLE exercises ADD COLUMN subcategory_key TEXT;
ALTER TABLE exercises ADD COLUMN pedagogical_stage TEXT;
ALTER TABLE exercises ADD COLUMN estimated_seconds INTEGER DEFAULT 0;
ALTER TABLE exercises ADD COLUMN primary_fen TEXT;
ALTER TABLE exercises ADD COLUMN solution_pgn TEXT;
```

Caso o SQLite não permita `ALTER TABLE` repetido com segurança no ambiente atual, criar função de migration que verifica `PRAGMA table_info(exercises)` antes de adicionar cada coluna.

### 19.3 Métodos novos esperados em `Database`

```python
# Materiais
create_pedagogical_material(**payload) -> int
get_pedagogical_material(material_id: int) -> dict | None
update_pedagogical_material(material_id: int, **payload) -> None
list_pedagogical_materials(club_id: int, filters: dict) -> list[dict]

# Versões
create_pedagogical_material_version(**payload) -> int
get_next_material_version_number(material_id: int) -> int
list_material_versions(material_id: int) -> list[dict]

# Assets
create_asset_file(**payload) -> int
create_asset_file_from_path(...) -> int
get_asset_file(asset_file_id: int) -> dict | None
link_exercise_asset(**payload) -> int

# Posições
get_chess_position_by_fen(normalized_fen: str) -> dict | None
create_chess_position(**payload) -> int

# PDFs/jobs
create_pdf_generation_job(**payload) -> int
get_pdf_generation_job(job_id: int) -> dict | None
update_pdf_job(job_id: int, **payload) -> None
create_pdf_output(**payload) -> int
get_pdf_output(output_id: int) -> dict | None

# Progresso
record_pedagogy_attempt(**payload) -> int
upsert_spaced_repetition_review(**payload) -> None
get_member_progress(member_id: int, filters: dict) -> dict
```

---

## 20. Testes

### 20.1 Testes unitários prioritários

| Arquivo | Testes |
|---|---|
| `test_chess_validation.py` | FEN válida, FEN vazia, FEN mal formatada, posição ilegal, PGN válido, PGN inválido, múltiplos jogos. |
| `test_diagram_render.py` | Geração SVG, cache, FEN inválida, orientação invertida. |
| `test_pedagogy_materials.py` | Criar, atualizar, versionar, rejeitar tipo inválido, exigir permissão. |
| `test_assets.py` | Upload válido, extensão inválida, tamanho excedido, hash duplicado. |
| `test_pdf_generation.py` | Criar job, gerar PDF, falha de template, falha de dados, status final. |
| `test_progress.py` | Cálculo de acerto, atualização de revisão, recomendações. |

### 20.2 Exemplos de pytest

```python
def test_validate_fen_start_position():
    result = ChessValidationService.validate_fen(
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    )
    assert result["valid"] is True
    assert result["side_to_move"] == "white"
    assert result["legal_moves_count"] == 20


def test_validate_fen_rejects_empty():
    with pytest.raises(AppError):
        ChessValidationService.validate_fen("")


def test_parse_pgn_valid_game():
    pgn = "1. e4 e5 2. Nf3 Nc6 *"
    result = ChessValidationService.parse_pgn(pgn)
    assert result["game_count"] == 1
    assert result["games"][0]["ply_count"] == 4
```

### 20.3 Testes de integração

1. Criar material.
2. Criar versão inicial.
3. Criar exercício com FEN.
4. Renderizar diagrama.
5. Criar lista de treino.
6. Solicitar PDF.
7. Rodar worker.
8. Baixar PDF.
9. Confirmar registro em `pdf_outputs`.
10. Registrar tentativa do aluno.
11. Confirmar atualização de revisão espaçada.

### 20.4 Critérios de aceite de PDF

1. PDF abre sem erro.
2. Tem cabeçalho com nome do clube/material.
3. Diagramas aparecem centralizados e legíveis.
4. Versão sem soluções não mostra resposta.
5. Versão com soluções mostra solução e comentário.
6. Rodapé tem paginação.
7. Exercícios não quebram de forma ruim entre páginas quando possível.
8. Job finaliza como `succeeded`.
9. Falha de template marca job como `failed` com erro legível.

---

## 21. Roadmap de implementação

### Fase 0 - Preparação técnica

**Entrega:** branch, migrations vazias, feature flag, documentação inicial.  
**Duração estimada:** 2 a 3 dias.

Tarefas:

1. Criar branch `feature/pedagogical-module`.
2. Criar diretórios novos.
3. Criar migration inicial.
4. Criar feature flag `ENABLE_PEDAGOGY_MODULE`.
5. Adicionar permissões no seed.
6. Criar testes vazios.

### Fase 1 - Núcleo de xadrez

**Entrega:** validação FEN/PGN e render SVG.  
**Duração estimada:** 1 semana.

Tarefas:

1. Implementar `ChessValidationService`.
2. Implementar `DiagramRenderService`.
3. Criar endpoints `/chess/validate-fen`, `/chess/validate-pgn`, `/chess/render-diagram`.
4. Criar testes unitários.
5. Integrar preview no frontend.

### Fase 2 - Materiais e assets

**Entrega:** CRUD de materiais, versões e anexos.  
**Duração estimada:** 1 a 2 semanas.

Tarefas:

1. Criar tabelas `pedagogical_materials`, `versions`, `items`, `asset_files`.
2. Implementar `PedagogicalMaterialService`.
3. Implementar `ExerciseAssetService`.
4. Implementar upload seguro.
5. Criar UI básica de listagem/edição.

### Fase 3 - Geração de PDF

**Entrega:** PDF de lista de treino e material.  
**Duração estimada:** 2 semanas.

Tarefas:

1. Criar templates `base.html`, `exercise_sheet.html`, `solution_sheet.html`.
2. Implementar `pdf_generation_jobs`.
3. Implementar `PDFGenerationService`.
4. Implementar worker simples.
5. Criar painel de status no frontend.
6. Testar PDFs com exercícios reais.

### Fase 4 - Importação PGN

**Entrega:** upload/importação de PGN com relatório.  
**Duração estimada:** 1 a 2 semanas.

Tarefas:

1. Implementar `PGNImportService`.
2. Criar job de importação.
3. Salvar `pgn_games`.
4. Permitir transformar jogo em material/partida comentada.
5. Preservar comentários e NAGs.

### Fase 5 - Progresso e recomendações

**Entrega:** dashboard pedagógico e revisão espaçada.  
**Duração estimada:** 2 a 3 semanas.

Tarefas:

1. Estender `record_attempt`.
2. Criar `spaced_repetition_reviews`.
3. Implementar cálculo de progresso.
4. Implementar recomendações.
5. Criar dashboard do aluno/professor.

### Fase 6 - Endurecimento de produção

**Entrega:** estabilidade, logs, backups, monitoramento e otimização.  
**Duração estimada:** 1 a 2 semanas.

Tarefas:

1. Migrar worker simples para RQ ou Celery.
2. Adicionar retries e monitoramento.
3. Adicionar limpeza de arquivos órfãos.
4. Adicionar testes E2E.
5. Revisar permissões.
6. Criar manual técnico e manual do usuário.

---

## 22. Riscos e mitigação

| Risco | Impacto | Mitigação |
|---|---:|---|
| WeasyPrint exigir libs do sistema | Médio | Documentar instalação; manter fallback ReportLab ou Playwright PDF. |
| PGNs grandes demorarem | Alto | Importação via job, streaming e limite por arquivo. |
| SVG quebrar no PDF | Médio | Converter SVG para PNG quando necessário. |
| Permissões incompletas | Alto | Testes de acesso por clube e papel. |
| Duplicação de arquivos | Médio | Hash SHA-256 por clube. |
| PDF síncrono causar timeout | Alto | Sempre usar `pdf_generation_jobs`. |
| Parser PGN aceitar erro silencioso | Alto | Verificar `game.errors` e gerar relatório. |
| Materiais publicados serem alterados sem histórico | Médio | Versionamento obrigatório. |
| Frontend divergir do backend | Médio | Backend é fonte de verdade; frontend só pré-valida. |
| SQLite limitar concorrência | Médio | Usar jobs curtos no MVP; planejar PostgreSQL para escala. |

---

## 23. Checklist de implementação

### Banco

- [ ] Criar tabelas de materiais.
- [ ] Criar tabelas de versões.
- [ ] Criar tabelas de assets.
- [ ] Criar tabelas de posições.
- [ ] Criar tabelas de PGN.
- [ ] Criar tabelas de jobs PDF.
- [ ] Criar tabelas de outputs PDF.
- [ ] Criar índices.
- [ ] Criar seed de permissões.

### Backend

- [ ] Implementar `ChessValidationService`.
- [ ] Implementar `DiagramRenderService`.
- [ ] Implementar `PedagogicalMaterialService`.
- [ ] Implementar `ExerciseAssetService`.
- [ ] Implementar `PDFGenerationService`.
- [ ] Implementar `PGNImportService`.
- [ ] Implementar `PedagogyProgressService`.
- [ ] Implementar `PedagogyRecommendationService`.
- [ ] Implementar rotas.
- [ ] Padronizar erros.

### Frontend

- [ ] Criar componente de FEN.
- [ ] Criar preview do tabuleiro.
- [ ] Criar importador PGN.
- [ ] Criar editor de material.
- [ ] Criar painel de geração PDF.
- [ ] Criar dashboard de progresso.

### PDF

- [ ] Criar template base.
- [ ] Criar folha sem solução.
- [ ] Criar folha com solução.
- [ ] Criar plano de aula.
- [ ] Criar partida comentada.
- [ ] Testar com diagramas.
- [ ] Testar com material longo.

### Testes

- [ ] Testes unitários de FEN.
- [ ] Testes unitários de PGN.
- [ ] Testes de upload.
- [ ] Testes de material/versionamento.
- [ ] Testes de PDF job.
- [ ] Testes de permissão.
- [ ] Testes de progresso.

---

## 24. Critérios de pronto

O módulo pode ser considerado pronto para a primeira versão quando:

1. Um professor consegue criar material pedagógico com título, nível, categoria e conteúdo.
2. Um professor consegue criar exercício com FEN validada.
3. O sistema gera diagrama SVG a partir da FEN.
4. O professor consegue montar lista de exercícios.
5. O sistema gera PDF sem solução.
6. O sistema gera PDF com solução.
7. A geração de PDF usa job com status consultável.
8. O PDF gerado fica registrado no banco e pode ser baixado.
9. Um aluno consegue registrar tentativa de exercício.
10. O dashboard mostra taxa de acerto por categoria.
11. Erros de FEN/PGN são claros e em português.
12. Permissões impedem acesso indevido entre clubes.
13. Testes unitários principais passam.
14. Testes de integração cobrem o fluxo completo.

---

## 25. Priorização recomendada

A ordem mais segura é:

1. **Validação FEN/PGN e renderização de diagramas.**  
   Sem isso, os materiais de xadrez ficam frágeis.

2. **Materiais pedagógicos e versionamento.**  
   Permite começar a organizar conteúdo sem esperar PDF completo.

3. **PDF assíncrono.**  
   Entrega valor prático para clube/professor.

4. **Importação PGN.**  
   Aumenta produtividade para livros e bases antigas.

5. **Analytics e revisão espaçada.**  
   Fecha o ciclo pedagógico.

---

## 26. Referências técnicas consultadas

- Documentação do `python-chess` sobre PGN, `read_game`, `mainline_moves`, headers e erros de parsing: https://python-chess.readthedocs.io/en/v1.5.0/pgn.html
- Documentação do `python-chess` sobre renderização SVG: https://python-chess.readthedocs.io/en/v0.24.0/svg.html
- Página oficial do WeasyPrint: https://weasyprint.org/
- Documentação oficial do FastAPI sobre `BackgroundTasks`: https://fastapi.tiangolo.com/tutorial/background-tasks/
- Documentação oficial do Celery sobre `apply_async`, `delay`, progresso e retries: https://docs.celeryq.dev/en/latest/userguide/calling.html

---

## 27. Conclusão técnica

A proposta original está correta na direção, mas ainda insuficiente para implementação segura. A versão recomendada neste documento transforma a ideia em um módulo implementável, com separação clara entre domínio pedagógico, validação enxadrística, renderização de diagramas, geração de PDF, armazenamento, permissões, jobs e progresso do aluno.

A maior mudança conceitual é tratar PDF, PGN grande e renderizações pesadas como processos assíncronos rastreáveis. A maior mudança estrutural é introduzir `asset_files`, `pedagogical_material_versions`, `chess_positions`, `pdf_generation_jobs` e `pdf_outputs`. A maior correção técnica é robustecer FEN/PGN com `python-chess`, verificando erros reais de parsing e calculando material manualmente.

Com essa base, o módulo deixa de ser apenas um cadastro de exercícios e passa a ser uma estrutura pedagógica completa para clubes de xadrez: criação de conteúdo, impressão de material, treino com tabuleiro, histórico de aprendizado e recomendações de revisão.
