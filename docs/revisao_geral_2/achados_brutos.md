# Achados brutos — Revisão Geral 2 (condensado dos relatórios)

## R9 regressão no não commitado — sem P0/P1
- R9.1 P3 [E] tests/test_dup_check_tmp.py: rascunho sem assert (só print) — transformar em teste de duplicate_tournament ou apagar.
- R9.2 P3 [H] testes sem assert explícito: test_column_layouts.py:195, test_core_org04.py:156, test_ui_rgs28_scaling.py:102.
- Verificado OK: pares de acento produtor/consumidor; TRF largura fixa sem acento; migração de backups reais v44 e v55 → v59 integrity ok; funções removidas sem chamador; .spec/build.bat.
- Melhorias: partir diff em commits (acentos / infra exe / migrações / pareamento / UI / testes); scripts crap/dry/mutate rastreados; teste de contrato combo↔valor; .gitattributes eol; build+self-test antes do commit.
- Conferi: nenhum backup pre_migration novo foi gravado na pasta real (últimos de 11/11 e 15/05).

## R6 falhas silenciosas
- R6.1 P1 [E ordenação] tiebreaks.py:467 `int(item.get("_gacrux_rank") or 0)` — jogador sem rank do motor vai ao 1º lugar. Gatilho [H]: standings() sem up_to_round lista todos (pairing_service.py:4109) e TRF do motor usa players(up_to_round=rounds) (gacrux_tiebreak_engine.py:110); run descarta cid sem mapa (gacrux_tiebreak_engine.py:244-253; gacrux_tiebreak_map.py:243-245). Fix: ausência = falha do motor (AppError → fallback registrado); chave inf.
- R6.2 P1 [E] trf_import.py:306-330 perde jogo com adversário inexistente/assimétrico; letra desconhecida vira '' (results_registry.py:146) em rodada fechada; start_rank ilegível vira len+1 (trf_import.py:166-169) e colide em rank_to_id (import_service.py:406). Fix: warnings + AppError em rank duplicado.
- R6.3 P1 [E] import_service.py:1156-1162 _parse_optional_int: '1.850'→1, '1,850'/'abc'/'2 000'→0; usado em :590,:593,:735,:738,:1017,:1028; rating=max(nac,int) :749,:1041.
- R6.4 P2 [L] export_federation.py:245-249 except Exception: continue — rodada some do pacote Access.
- R6.5 P2 [L] access_export.py:92-121 .accdb parcial fica e conexão não fecha.
- R6.6 P2 [L] gacrux_tiebreak_engine.py:244-253 saída vazia → {} sem erro → rótulo "Gacrux" com cálculo próprio; _as_float ilegível→0.0 (gacrux_tiebreak_map.py:258-262).
- R6.7 P2 [L] tiebreak_criteria.py:308-336 sequência corrompida/código desconhecido → padrão sem aviso (pairing_service.py:4126).
- R6.8 P3 [L] arbitration.py:129-136 round_id inválido fail-open sem log.
- R6.9 P3 [L] rating/kfactor.py:39-43 k_override inválido volta ao regulamento sem aviso.
- R6.10 P3 [L] rating_service.py:380-382 JSON de federações corrompido → add_foreign_federation (:393-401) sobrescreve e apaga.
- R6.11 P3 [L] ui/screens/tournaments/pages.py:915-916 diálogo de ritmo engole exceção (debug).
- R6.12 P3 [L] export_web.py:703-704 QR falho → ""; import_service.py:645-657 nível inexistente → None; member_service.py:466-472 rating online inválido → 0; rating_service.py:442 errors="replace".
- Melhorias: estender teste RGS-32 a `return None/[]/0` e `continue`; tipo de retorno de importação com warnings; log em _savepoint; "recalcular agora" no cache de falha do desempate; ui/app.py:1093-1099 after com janela fechada.

## R7 segurança
- R7.1 P1 [L] result_server.py:12 bind 0.0.0.0; :58-68 `mode` da query e tournament_id do caminho sem checar publicado; export_web.py:103-133,203-230 modos clube/privado expõem contact_email, comments, fide_id. Fix: modo fixado em publish_tournament (self._portal_mode), 404 se id != publicado.
- R7.2 P1 [E] export_writers.py:102-106,140-144,174-178 injeção de fórmula XLSX/CSV (=HYPERLINK vira data_type 'f'). Fix: neutralizar_celula prefixa ' em = + - @ \t \r.
- R7.3 P2 [L] permissões só na tela: só security_service chama require_permission; tournament_service.py:206 delete_tournament, finance_service.py:280,:347, deletes de membros sem checagem; delete_records não usado.
- R7.4 P2 [L] sync_service.py:163-168 payload_hash vazio = válido, SHA-256 sem chave; secret_hash nunca verificado; register_device sem permissão. Latente (sem rota que chame apply_remote_event).
- R7.5 P2 [L] legacy_migrations.py:783-796 admin/admin padrão sem troca obrigatória.
- R7.6 P2 [L] import_service.py:782,828 CSV só utf-8-sig, UnicodeDecodeError cru; :800-801,:851 response.read() sem teto. (TRF tem fallback latin-1 :337-340.)
- R7.7 P3 [L] qr_result_service.py:262-265 HMAC com chave sha256(operator_name+db_path).
- R7.8 P3 [L] result_server.py:44 submitter sem limite; qr_result_service.py:125-141.
- R7.9 P3 [H] education_service.py:768-808 Paragraph do reportlab sem escape (< & quebram PDF).
- R7.10 P3 [L] database.py:1230-1260 _protect_secret DPAPI falha → texto puro calado.
- R7.11 P3 [L] "Listas Jogadores CBX/ListaJogadoresEmDiaCBX.xls" versionado (dados pessoais); docs/CNAME.
- R7.12 P3 [L] ui/app.py:394 strip na senha do login × create_user sem strip; papel não validado; sem limite de tentativas.
- Melhorias: cabeçalhos CSP/no-store no portal; quote em src da galeria FTP; log do Gacrux sem TRF completo (gacrux_engine.py:~596); checagem de client_secret no build; auditar login falho.
- OK: subprocess Gacrux sem shell; SQL com ?; sem pickle/eval; restore confinado; html.escape; _safe_name; PBKDF2 210k.

## R8 organização/clube/prêmios (scripts r8/t1..t5.py)
- R8.1 P1 [E] categoria gravada no jogador não é recalculada quando muda o edital/data de referência/data do torneio. database_tournament_core.py:600-635 replace_tournament_categories; cálculo só em create/update_player (:1121,:1272,:1380); classificação lê coluna (tiebreaks.py:512). Fix: _refresh_player_categories na mesma transação.
- R8.2 P1 [E] "apenas o maior prêmio" não repassa e soma categorias: prizes.py:139-143,146-176,207-214. Ex.: geral 100 + 3×50 no mesmo jogador → leva 150, 100 do geral a ninguém; distribui 150 de 250. Fix: alocação sequencial + undistributed.
- R8.3 P1 [E] duplicar torneio: database_tournament_core.py:172-360 não copia tournament_categories, prize_tie_split, prize_exclude_withdrawn, category_reference_date, late_tolerance_minutes; copia archived (:264) → novo some da lista.
- R8.4 P1 [E] inscrição a partir de membro: database_members.py:521-541 passa category do membro (calculada no ano corrente) e não passa sexo; members sem coluna sex (database_schema.py:56-85); assignment.py:126-134 trata como manual → categoria fantasma "Sub-12" fora do edital e Feminino nunca. Modo Livre friendly_mode.py:191-195.
- R8.5 P1 [E] "Sub-12" não aceita mais novo: assignment.py:66-95; core/categories.py:182-185. Menino 2017 1º lugar não leva Sub-12.
- R8.6 P2 [L] prizes.py:41-45,109-129 só equal/hort; falta "desempate decide" (indivisível).
- R8.7 P2 [L] certificate_service.py:318-326,1007-1014,1025 diploma por categoria usa só categoria principal, ignora exclude_withdrawn e empate.
- R8.8 P2 [E] member_service.py:168-195 desativar apaga lichess/chesscom/ratings online; :427-496 editar apaga departure_*; UPDATE completo database_members.py:154-230.
- R8.9 P2 [L] prize_service.py:58-60; prizes.py:154-160 prêmio de categoria com nome inexistente aceito e some.
- R8.10 P2 [L] friendly_mode.py:219-247 desligar Modo Livre após jogado libera rating/TRF sem pergunta (trf16.py:64; rating_service.py:810-814).
- R8.11 P3 [E] tournament_service.py:176-206 categoria impossível (15 a 12, sexo vazio) aceita.
- R8.12 P3 [L] rest_day sem efeito (tournament_settings_ui.py:862; generate_round_schedule tournament_service.py:1068-1133); _validated_schedule (:1001-1066) aceita R3 antes da R2.
- Melhorias: membro duplicado; record_attendance (education_service.py:50-79) sem transação e sem desmarcar; reference_year fallback created_at (core/categories.py:63-69); total anunciado × distribuído; update_tournament_details apaga agenda acima do total (database_tournament_core.py:164-170).
- OK: is_withdrawn, Hort, bordas idade/rating, mensalidade idempotente, date_review, add_round/late_entry em transação.

## R4 UI árbitro (sondas r4/test_probe_r4.py, run.py)
- R4.1 P1 [E] Enter na tabela de Rodadas grava em duas mesas: view.py:377 bind <Return> sem "break" + view.py:726 bind na raiz. W.O. confirma 2× e grava 2 mesas; rodada fechada abre correção 2×. Fix: retornar "break".
- R4.2 P1 [E] auto-refresh do painel (15 s) zera seleção e rouba foco: pairing_arbitration/refresh.py:59-66, pending.py:201,206,144 → tecla "1" grava 1-0 na mesa 1 (não a selecionada) / digitação na busca vira resultado.
- R4.3 P1 [E] viewer grava pelo painel: app.py:605 aba Árbitro sem permissão; pending.py:277 save_result, :298 postpone; registry.py:184,197 byes/ajustes/proibições; issues.py:237-262; pairing_results/qr.py:64,74. (Liga com R7.3: serviços não checam.)
- R4.4 P1 [E] excluir bye solicitado já usado: controller.py:238 delete_bye chama db direto; sem regra/auditoria; saldo zera; request_bye conta por list_requested_byes (pairing_service.py:1049) → bye acima do limite.
- R4.5 P2 [E] "Todos presentes" initial_call.py:210-232 sem transação; desistente para o laço no meio; reload (:157) perde seleção.
- R4.6 P2 [L] "Retirar do torneio…" com mesa aberta: player_actions/dialogs.py WithdrawDialog não avisa nem oferece W.O. (set_player_participation pairing_service.py:934).
- R4.7 P2 [L] tabela de Rodadas sem menu do jogador (view.py:386).
- R4.8 P2 [L] lançamento pelo painel sem Desfazer (pending.py:277-296).
- R4.9 P3 [L] duplo clique no painel abre a primeira pendente (pending.py:185).
- R4.10 P3 [L] swaps.py sem busca; troca por equipes sem motivo.
- Melhorias: cursor após salvar = próxima linha; texto BYE de equipes; auto-refresh pausa com diálogo/foco + indicador; rejeitar QR sem confirmação (qr.py:148, issues.py:244); destacar mesa-alvo nas teclas do painel.
- OK: Ctrl+Z, W.O. por tecla, diálogo de correção, fechar rodada, excluir rodada, after com guarda.

## R2 dados (scripts r2/*.py)
- R2.1 P1 [E] retenção de backups apaga o banco vivo: database.py:1125-1149 list_backups glob *.db + prune unlink; settings.py:290-319 aceita backup_dir = pasta do .db. (prune_live.py: albericus.db apagado). Fix: filtrar f"{stem}_*", nunca self.db_path, recusar backup_dir == db_path.parent.
- R2.2 P1 [E] excluir jogador de equipes zera tabuleiro jogado: pairing_service.py:3715-3729 só conta pairings (database_tournament_core.py:1985-1995); team_boards ON DELETE SET NULL (database_schema.py:503-504); team_substitution_events CASCADE (:557). tournament_players/controller.py:164.
- R2.3 P1 [E] dividir torneio: tournament_service.py:586 `bye_points or 1.0` → bye 0 vira 1; laço :573-619 sem transação; não copia rapid/blitz/games_played. Mesmo padrão `team_match_draw_points or 1.0` pairing_service.py:3444-3478 [L].
- R2.4 P1 [E] fechar rodada por equipes não idempotente nem atômico: pairing_service.py:3422-3529 (2 eventos/2 backups; rodada fechada sem retrato). RGS-11 só no individual (:2816,:2848).
- R2.5 P2 [E] retenção apaga primeiro before_schema_migration/before_restore (database.py:1140-1149); 9 rodadas ≥ 18 backups; padrão 10.
- R2.6 P2 [E] allowed_keys database.py:1297-1336 descarta import_mapping_profiles (import_service.py:311,319) e registration_form_prefill_base/registration_form_tournament_entry (export_players.py:238) sem erro.
- R2.7 P2 [E] bye/late_entry_points sem faixa: tournament_service.py:676-681, :821 → 'inf','7','0,3','-1' gravados; 'nan' IntegrityError cru.
- R2.8 P2 [E] várias gravações sem transação: set_player_participation pairing_service.py:960-982; geração individual :1584-1636 (rodada sem evento/status); [L] forfeit_absent_player :1258-1267; qr approve_submission :157-174; apply_tournament_ratings rating_service.py:817-819.
- R2.9 P2 [L] excluir torneio sem backup nem rastro: tournament_service.py:206-211; database_tournament_core.py:362-364; audit_events CASCADE (database_schema.py:814).
- R2.10 P3 [E] poda ordena por segundo (database.py:1137) → pode apagar o mais novo.
- R2.11 P3 [L] Gacrux dentro de BEGIN IMMEDIATE no close_round (pairing_service.py:2848-2860) → database is locked para QR/reconciliação.
- R2.12 P3 [L/H] sem trava de instância única; qr submit_result (:110-142) duplica envio (sem UNIQUE).
- Melhorias: parse_points() único (tournament_service.py:677,821,861,875); varredura `.get(...points...) or N`; suíte de migração com backups reais anonimizados; retenção por tipo; sync apply_remote_event sem chamador.
- OK: transaction()/SAVEPOINT reentrante; MigrationEngine por versão; backups reais v44/v55→v59 ok; restore; reconciliação; import TRF em transação; exclusão de rodada.

## R5 exportações/federação (scripts r5/t1..t9)
- R5.1 P1 [E] TRF16/25 grava rating local como FIDE: export_federation.py:629-635 _trf_rating = international or rating or national; usado 001 col 49-52 (:876), 072 (trf16.py:174, trf25.py:227), aviso (trf16.py:382); reimport grava international_rating (import_service.py:400-401). Fix: _trf_fide_rating só international.
- R5.2 P1 [E] normas/IT3 tratam adversário sem FIDE como ratado: rating/report.py:25-27 cadeia termina em ("rating","geral"); norms/report.py:62-64; export_federation.py:197. 9 GM com rating local 2500 → norma GM "atingida".
- R5.3 P1 [E] normas: federação vazia escapa limites: norms/opponents.py:133,:180-182; norms/evaluation.py:128-137 own="". Fix: federation_id or settings.federation.
- R5.4 P1 [E] importar TRF em andamento fecha rodada sem resultado e encurta torneio: import_service.py:409-418 close_round em toda rodada; trf_import.py:194,202 ignora 142/XXR.
- R5.5 P2 [E] trf_import.py:86-87 break na 1ª célula vazia → entrante tardio perde rodadas.
- R5.6 P2 [E/L] sexo exportado 'f' (export_federation.py:873) em vez de 'w'; norms/handbook.py:119 só reconhece 'F'; trf_import.py:176 grava 'w'.
- R5.7 P2 [E] rating_service.py:70,:482 CSV de lista oficial só utf-8-sig.
- R5.8 P2 [E] PDFs sem TTF: Ł/Ć/Ş/ễ → ■ (IT3 precisa de estrangeiros).
- R5.9 P2 [E/H] "ASCII" do TRF deixa Ø Ł ß æ (export_federation.py:564-570; trf25_records.py:31-35); grava UTF-8 (trf16.py:72).
- R5.10 = R7.2 fórmula CSV/XLSX.
- R5.11 P2 [E] lista FIDE acumula snapshot inteiro a cada importação: database_tournament_core.py:886-914; fide_list.py:95-117 (≈168 B/jogador/importação).
- R5.12 P3 [E] TRF25 individual sai "082 0" (trf25.py:229), 102 sem FIDE ID do árbitro (:231-233 × trf16.py:184-188), _file_problems não roda; diploma nome 30 pt fixo (certificates/renderer.py:161; fit_font_size não chamado).
- Melhorias: fide_dp arredondamento bancário (rating/tables.py:59) [H]; OfficialRatingService.compute_report/save_report só teste (rating_service.py:1065-1089); exceções 1.4.3 das normas [H]; slug colide no lote (batch_export_service.py:31); TRF25 grava direto no destino (trf25.py:220).
- OK: posições 001/células/132/013 TRF16; tabelas B.02; limiares B.01; escape HTML; _safe_filename.

## Conferência própria (eu)
- R4.1 reconfirmado [E]: ENTER -> ['1/2-1/2','1/2-1/2','',''], 2 result_updated.
- R4.2 reconfirmado [E]: seleção após tick 0 (antes 2).
- R4.4 reconfirmado [E]: saldo "1 usado" → "nenhum usado", mesa continua H, sem evento de remoção.
- R2.1 lido [L]: database.py list_backups glob *{suffix}; prune só checa sufixo. Confere.
- R6.1 lido [L]: tiebreaks.py gacrux_key int(_gacrux_rank or 0). Confere; gatilho em produção segue [H].
- R5.1 lido [L]: export_federation._trf_rating international or rating or national. Confere.

## R3 emparceiramento (scripts r3/team_stress.py, late.py, stress.py, stress_patched.py, two.py) — artigos FIDE de memória
- R3.1 P1 [E] suíço por equipes repete confronto evitável: team_swiss.py:597-674 (3º passe aceita repetição como custo; return [], group), :736-756 optimal/greedy só penalizam; bye antes da viabilidade (constraints.py:271-288), todas com bye → 2º PAB calado. 7 equipes×6 rodadas: 5/10 sementes repetem com alternativa; 6×5: 2/6. Também BBWWW [H para equipes].
- R3.2 P1 [E] = R6.1 com gatilho confirmado: entrante tardio em 1º na classificação ao vivo (late.py: [('Tardio',1.0),('J2',2.0),...]); tiebreaks.py:470-486; gacrux_tiebreak_engine.py:107 players(up_to_round=rounds) exclui entry_round > fechadas.
- R3.3 P2 [E] regressão RGS-24×RGS-16: gacrux_trf.py:259 with_round_cells patched.rstrip() come a coluna de resultado da rodada recém-gerada → Gacrux -c 502 → pairing_check_unverified em todas as rodadas após entrada tardia com pontos (3/3 sementes); sem rstrip 0 problemas.
- R3.4 P2 [E] sem pareamento legal: gacrux_engine.py:282-284 AppError com Traceback cru, não GacruxRefusal; reserva também falha (2 jogadores R2; 3 jogadores R4).
- R3.5 P2 [L] equipes pareadas por match_points fixo (team_swiss.py:716; constraints.py:238-250) ignora team_standing_primary (team_tiebreaks.py:272).
- R3.6 P2 [L] gacrux_tiebreak_engine.py:103 swiss = method != "round_robin" → Scheveningen/eliminatória com -s (adversário virtual C.07 §16).
- R3.7 P3 [L] `team_match_draw_points ... or 1.0` database_tournament_core.py:541; pairing_service.py:2560/3446/3482; team_swiss.py:380 (= R2.3 padrão).
- Melhorias: aviso quando falta rank do Gacrux; teste reconcile_scores/rebased_score_lines com célula pendente; stress de equipes em -m gacrux; fixar initial_color nos testes de pareamento; choose_team_bye recusar sem elegível.
- OK: individual Gacrux 8 sementes × 7 rodadas sem reencontro/PAB repetido/3 cores; reserva; checker; 162/299/260/152.

## R1 executada (eu)
- Gate -Fast: compilação, ruff, mypy, convenções UI, acentuação (1869 textos, 267 palavras) — todos OK.
- Suíte completa com coverage: 2409 passaram, 5 pulados, 0 falhas. Cobertura src 66,5%.
- Crapper (src sem gacrux): 3450 funções, 431 com CRAP >= 10. Piores: rating_service.import_official_excel 1211 (cc35 cob1%); tiebreaks.tiebreak_narrative_from_standings 552; education export_collection_pdf 402 / html 251; import_service.import_rating_list_csv 198 (cob 2%); export_federation.export_pgn 165; tournament_service._validated_settings 156 (cc70); rating_service._tabular_rows 107; access_export.write_accdb 105; tournament_settings_ui.show_tournament_settings 100 (cc79); import_service._member_payload_from_row 100 (cob 3%); late_entry.lookup 91; swaps.open_player_swap 83; _import_member_rows 66 (cob 3%).
  → os importadores (CSV, rating, membros) estão quase sem cobertura: casa com R6.2, R6.3, R7.6, R5.7.
- Dryer 0.8 min-tokens 40: 878 pares, quase todos wrappers de SQL (list_*) que só diferem no texto — não vale eliminar. Com min-tokens 150: 38 pares. Relevantes: constraints.optimal_player_pairs ↔ optimal_team_pairs 0.99; fide_dutch.dutch_bracket_pairing ↔ team_swiss.dutch_team_bracket_pairing 0.96; search_dutch_pairing ↔ search_dutch_team_pairing 0.92; solve ↔ solve 0.88 → a cópia de equipes é a que repete (R3.1): uma decisão, um lugar. Outros: fetch_lichess/chesscom 1.00; show_rating_history 0.98 (2 telas); create/update_* 0.92-0.98; _round_robin_round ↔ _scheveningen_round 0.89; trf25 _requested_bye_records_240 ↔ team 0.91; export_pairings ↔ export_list 0.90.
