# ESPEC — Reformulação dos Diplomas (Albericus)

Documento de planejamento da reforma do módulo de Diplomas/Certificados.
Iniciado em 2026-06-12. Princípio inegociável: **tudo rigidamente modularizado**
(puro separado de I/O; pacote com submódulos focados; serviço como fachada).

## 1. Problema

O renderizador atual (`CertificateService._draw_certificate_page`) desenha um
layout genérico e plano: duas bordas retangulares, tudo em Helvetica, nome do
premiado diluído no parágrafo, paleta azul+azul-claro, zero identidade de
xadrez, sem selo/medalha. Trocar cor/logo/fonte (já possível) não resolve,
porque a *estrutura desenhada* é fixa.

## 2. Objetivos (tudo o que foi acordado)

1. **10 presets de estilo** selecionáveis: `classic`, `playful`, `modern`,
   `elegant`, `vintage`, `royal`, `laurel`, `geometric`, `kids`, `mono`.
2. **Renderizador rico**: nome como herói (serifa), banner, moldura ornamental,
   selo/roseta vetorial, marca d'água, **medalha ouro/prata/bronze conforme a
   colocação** (some em participação/treino).
3. **Toggles**: selo on/off, marca d'água on/off.
3b. **Marca d'água flexível** (corrige o cavalo ambíguo): peça de xadrez
   vetorial à escolha (`rook`, `king`, `knight`, `pawn`), padrão de tabuleiro,
   numeral da colocação, **ou imagem importada pelo usuário** (brasão/logo do
   clube), com opacidade configurável. Ver §5b.
4. **Modo "imagem de fundo padronizada"**: o usuário cria a arte fora (Canva,
   etc.) no **tamanho padrão** que o gerador documenta/exporta como guia,
   importa e só preenche os **dados sobrepostos** (nome, colocação, data…).
5. **50 modelos prontos** distribuídos nos 3 estilos × tipos de certificado.
6. **Visualizador embutido**: grade de miniaturas + preview ao vivo ao trocar
   estilo/cor/toggle, sem precisar abrir o PDF.

## 3. Arquitetura modular (pacote novo `src/services/certificates/`)

Cada arquivo tem uma responsabilidade. Nada de inchar `certificate_service.py`
— ele vira **fachada fina** (recipients, emissão, persistência) que delega o
desenho ao pacote.

| Módulo | Responsabilidade | Puro? |
|--------|------------------|-------|
| `surface.py` | Interface `DrawingSurface` + `ReportLabSurface` (PDF) e `TkSurface` (preview). Desacopla o desenho do backend. | não (backends) |
| `shapes.py` | Primitivas vetoriais: peça de xadrez, selo/roseta, coroa, medalha, faixa/cantos de tabuleiro, molduras. Desenha **contra a Surface**. | quase |
| `styles.py` | Presets (`classic/playful/modern`): fontes, ornamentos, flags. | sim |
| `palettes.py` | Paletas de cor nomeadas (insumo dos 50 modelos). | sim |
| `layout.py` | Cálculo de posições/frames por preset + orientação. | sim |
| `text.py` | Substituição de variáveis (`{nome}`, `{posicao}`…) e escape. | sim |
| `renderer.py` | Orquestra UMA página "generated" (styles+shapes+layout+surface). | não (usa Surface) |
| `overlay.py` | Modo `image_overlay`: sobrepõe campos sobre a imagem importada. | não |
| `gallery.py` | Gera os 50 modelos (preset × paleta × tipo → lista de dicts). | sim |
| `standard_size.py` | Dimensões padrão + geração do **guia de arte** importável. | quase |

Benefício-chave: o **mesmo** `renderer.py` produz PDF (ReportLabSurface) **e**
miniatura do visualizador (TkSurface). Um código de desenho, dois destinos.

Fontes: apenas as **built-in do ReportLab** (Helvetica, Times, Courier) — sem
depender de TTF externas. Serifa = Times.

## 4. Modelo de dados — migração de schema v42 → v43

Novas colunas em `certificate_templates` (todas com default retrocompatível,
migração idempotente no padrão `_ensure_*_schema`):

- `style_preset TEXT NOT NULL DEFAULT 'classic'` — um dos 10 presets
- `template_kind TEXT NOT NULL DEFAULT 'generated'` — generated | image_overlay
- `palette_key TEXT NOT NULL DEFAULT ''` — paleta nomeada (vazio = usa primary/accent)
- `seal_enabled INTEGER NOT NULL DEFAULT 1`
- `watermark_enabled INTEGER NOT NULL DEFAULT 1`
- `watermark_kind TEXT NOT NULL DEFAULT ''` — '' = padrão do preset; senão piece | board | numeral | image | none
- `watermark_piece TEXT NOT NULL DEFAULT ''` — rook | king | knight | pawn (quando kind=piece)
- `watermark_image_path TEXT NOT NULL DEFAULT ''` — imagem importada (quando kind=image)
- `watermark_opacity REAL NOT NULL DEFAULT 0.08` — 0..1
- `medal_by_placement INTEGER NOT NULL DEFAULT 1`
- `field_layout_json TEXT NOT NULL DEFAULT ''` — posições dos campos no modo imagem

Atualizar: DDL em `database_schema.py`, `create/update_certificate_template`,
`_validated_template_payload`, `DEFAULT_CERTIFICATE_TEMPLATES`, snapshot da API
pública e `SCHEMA_VERSION = 43`.

## 5. Tamanho padrão para imagens importadas

- **A4 paisagem @ 300 DPI = 3508 × 2480 px** (retrato = 2480 × 3508).
- Área segura: margem de ~10 mm (≈ 118 px) sem texto crítico nas bordas.
- `standard_size.py` exporta um **guia** (PNG/PDF transparente com a margem e as
  zonas de nome/colocação/assinaturas marcadas) — o usuário desenha por baixo,
  exporta no mesmo tamanho e importa. O gerador sobrepõe os dados nas zonas.

## 5b. Importador de imagem para marca d'água

Distinto do **fundo** (`background_image_path`, que cobre a página inteira): a
marca d'água é **central e sutil**. O usuário importa um PNG/JPG (de preferência
PNG com transparência — brasão/logo do clube), e o gerador a desenha no centro,
escalada para ~50% da menor dimensão, com `watermark_opacity` (0..1).

- Mecânica: `watermark_kind='image'` + `watermark_image_path`; o `renderer`
  delega a `surface.image(...)` (já existe) numa zona central segura.
- Reaproveita a validação de caminho de imagem já presente no `CertificateService`.
- A marca d'água **vetorial** (peça/tabuleiro/numeral) continua como padrão por
  preset — `watermark_kind=''` usa o padrão; o importador é o caminho `image`.
- Correção do "cavalo ambíguo": peças redesenhadas como silhuetas limpas
  (`rook`, `pawn`, `king`, `knight`) em `shapes.py`; cada preset escolhe a sua.
- UI (Fase 5): seletor de tipo de marca d'água (peça / tabuleiro / numeral /
  imagem / nenhuma) + botão "Importar imagem" + slider de opacidade, com preview.

## 5c. Os 10 estilos

| preset | tom | fonte | moldura | selo | marca d'água padrão |
|--------|-----|-------|---------|------|---------------------|
| classic | navy + ouro | serifa | régua dupla + cantos de tabuleiro | roseta | torre |
| playful | multicolor escolar | sans bold | arredondada | medalha | tabuleiro |
| modern | minimalista | sans | barra lateral | — | numeral |
| elegant | preto + ouro | serifa | régua fina + florões | anel | rei |
| vintage | sépia/pergaminho | serifa | régua dupla + florões | roseta | torre |
| royal | borgonha + ouro | serifa | ornamentada | roseta + coroa | rei |
| laurel | verde + ouro | serifa | régua dupla | roseta + louros | tabuleiro |
| geometric | blocos vivos | sans bold | faixa de casas | anel | tabuleiro |
| kids | doce/vibrante | sans bold | arredondada | medalha + estrelas | peão |
| mono | p&b + 1 acento | sans | faixa de casas | anel | tabuleiro |

## 6. Roadmap (fases modulares, cada uma commit + verde)

- **Fase 1 — Núcleo de desenho** (sem schema): `surface`, `shapes`, `styles`,
  `palettes`, `layout`, `text`, `renderer`. Saída: 6 PDFs de amostra (3 presets
  × premiação/participação) com preset passado explicitamente. Checkpoint visual.
- **Fase 2 — Schema v43 + fachada**: colunas novas, defaults, validação;
  `certificate_service` integra preset/toggles e delega ao `renderer`.
- **Fase 3 — Galeria de 50 modelos**: `gallery.py` + ação "Gerar galeria" /
  seed; nomes e distribuição (≈17/17/16) cobrindo os 7 tipos de certificado.
- **Fase 4 — Modo imagem**: `standard_size` (guia exportável) + `overlay`
  (campos sobre imagem) + `template_kind=image_overlay` na fachada/UI.
- **Fase 5 — Visualizador**: `TkSurface` + grade de miniaturas + preview ao vivo
  em `settings_certificates_ui.py` (trocar preset/cor/toggle re-renderiza).
- **Fase 6 — Fechamento**: testes finais, mypy(src/core), commit, PR.

## 7. Testes / gate

- Puros (sem reportlab): `styles`, `palettes`, `gallery` (50 itens, distribuição,
  unicidade de nome), `layout`, `text`, `standard_size`.
- Render smoke: cada preset gera PDF sem erro; `image_overlay` sobrepõe campos.
- Migração v42→v43 (coluna nova + defaults preservados).
- Validação dos novos campos; snapshot da API pública.
- Gate do projeto: mypy em `src/core` limpo.

## 8. Decisões e pontos em aberto

- **Visualizador**: miniaturas via `TkSurface` (beziers aproximados por splines
  do Tk — suficiente para preview); PDF real continua fiel via ReportLab.
- **Modo imagem v1**: zonas de campo por posição padrão do tipo; editor visual
  de posições fica como evolução futura.
- **Medalha**: 1º=ouro, 2º=prata, 3º=bronze; demais colocações sem medalha;
  participação/treino/evento nunca exibem medalha.
