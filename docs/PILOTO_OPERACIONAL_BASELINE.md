# Piloto Operacional Simulado

Gerado em: 2026-06-01T01:59:28-03:00

Este relatório executa o fluxo crítico do árbitro em banco temporário.
Ele detecta regressões locais de desempenho, mas não substitui o teste
presencial com operadores, impressora e rede do evento.

## Resultado Automatizado

### Cenário com 121 jogadores

Status geral: **OK**

Mesas válidas na primeira rodada: 60

| Operação | Tempo | Limite | Status | Detalhes |
|---|---:|---:|---|---|
| Cadastrar inscritos | 570.6269 ms | 10000 ms | OK |  |
| Pré-visualizar primeira rodada | 14.2775 ms | 1000 ms | OK | 61 emparceiramentos planejados |
| Gerar primeira rodada | 75.3746 ms | 2000 ms | OK |  |
| Carregar painel do árbitro | 14.2522 ms | 500 ms | OK | 60 pendentes; 50 exibidos inline |
| Exportar lista de chamada PDF | 51.0615 ms | 5000 ms | OK | 4 páginas |
| Exportar súmulas PDF | 67.3316 ms | 5000 ms | OK | 60 páginas |
| Exportar mural PDF com QR | 602.9565 ms | 30000 ms | OK | 5 páginas |
| Lançar resultado e recarregar painel | 39.4836 ms | 250 ms | OK | media de 20 lançamentos |
| Fechar primeira rodada | 106.4533 ms | 5000 ms | OK |  |
| Calcular tabela cruzada | 9.0266 ms | 2000 ms | OK | 121 linhas |
| Exportar tabela cruzada HTML | 10.7942 ms | 2000 ms | OK | 15123 bytes |
| Criar backup final | 12.9309 ms | 5000 ms | OK | 1454080 bytes |
| Restaurar backup em segunda instalação | 622.2023 ms | 5000 ms | OK | 1 rodada; 61 mesas validadas |
| Validar continuidade offline | 866.7484 ms | 5000 ms | OK | painel, 4 resultados, fechamento, classificação, exportações e backup validados |
| Simular envios QR simultâneos e aprovar | 3099.6495 ms | 5000 ms | OK | 20 envios concorrentes recebidos e aprovados |
| Cadastrar inscrição de última hora e atualizar prévia | 45.1981 ms | 2000 ms | OK | 122 inscritos; 0,5 ponto; histórico preservado; jogador presente na prévia seguinte |
| Importar base oficial FIDE local | 29.4552 ms | 5000 ms | OK | 121 registros oficiais importados |
| Comparar ratings oficiais antes da rodada 1 | 139.2976 ms | 2000 ms | OK | 121 alterações; 0 sem correspondência; sem persistir |
| Confirmar correções oficiais selecionadas | 700.3101 ms | 10000 ms | OK | 121 alterações aplicadas seletivamente |
| Localizar mesa e lançar resultado pelo painel | 48.8176 ms | 1000 ms | OK | mesa 60 localizada fora do recorte inline, lançada e removida das pendências |

### Cenário com 801 jogadores

Status geral: **OK**

Mesas válidas na primeira rodada: 400

| Operação | Tempo | Limite | Status | Detalhes |
|---|---:|---:|---|---|
| Cadastrar inscritos | 3918.2690 ms | 10000 ms | OK |  |
| Pré-visualizar primeira rodada | 29.9748 ms | 1000 ms | OK | 401 emparceiramentos planejados |
| Gerar primeira rodada | 86.0819 ms | 2000 ms | OK |  |
| Carregar painel do árbitro | 23.0215 ms | 500 ms | OK | 400 pendentes; 50 exibidos inline |
| Exportar lista de chamada PDF | 67.8427 ms | 5000 ms | OK | 22 páginas |
| Exportar súmulas PDF | 419.1881 ms | 5000 ms | OK | 400 páginas |
| Exportar mural PDF com QR | 3701.6010 ms | 30000 ms | OK | 27 páginas |
| Lançar resultado e recarregar painel | 49.4234 ms | 250 ms | OK | media de 20 lançamentos |
| Fechar primeira rodada | 192.0668 ms | 5000 ms | OK |  |
| Calcular tabela cruzada | 23.9210 ms | 2000 ms | OK | 801 linhas |
| Exportar tabela cruzada HTML | 25.5569 ms | 2000 ms | OK | 96042 bytes |
| Criar backup final | 19.6087 ms | 5000 ms | OK | 4890624 bytes |
| Restaurar backup em segunda instalação | 699.9135 ms | 5000 ms | OK | 1 rodada; 401 mesas validadas |
| Validar continuidade offline | 860.8958 ms | 5000 ms | OK | painel, 4 resultados, fechamento, classificação, exportações e backup validados |
| Simular envios QR simultâneos e aprovar | 2846.3054 ms | 5000 ms | OK | 20 envios concorrentes recebidos e aprovados |
| Cadastrar inscrição de última hora e atualizar prévia | 117.0289 ms | 2000 ms | OK | 802 inscritos; 0,5 ponto; histórico preservado; jogador presente na prévia seguinte |
| Importar base oficial FIDE local | 146.0958 ms | 5000 ms | OK | 700 registros oficiais importados |
| Comparar ratings oficiais antes da rodada 1 | 882.3479 ms | 2000 ms | OK | 700 alterações; 101 sem correspondência; sem persistir |
| Confirmar correções oficiais selecionadas | 4325.6951 ms | 10000 ms | OK | 700 alterações aplicadas seletivamente |
| Localizar mesa e lançar resultado pelo painel | 73.5168 ms | 1000 ms | OK | mesa 400 localizada fora do recorte inline, lançada e removida das pendências |

## Validação Presencial Pendente

Execute ao menos um ensaio com árbitro e auxiliar usando o
[manual operacional](Manual_Operacional_Arbitragem.pdf).

- [x] Cronometrar inscrição de última hora (automatizado).
- [ ] Repetir inscrição de última hora com operador no computador do evento.
- [x] Cronometrar correção de rating oficial antes da rodada 1 (automatizado).
- [ ] Repetir correção de rating oficial com operador antes do evento.
- [ ] Confirmar legibilidade do mural impresso a distancia.
- [ ] Testar impressão de súmulas e cartões na impressora do evento.
- [x] Medir tempo para localizar e lançar resultado de uma mesa (automatizado).
- [ ] Repetir localização e lançamento de mesa com árbitro no evento.
- [x] Simular envio QR simultâneo e aprovação pelo árbitro (automatizado).
- [ ] Repetir envio QR simultâneo com celulares na rede local do evento.
- [x] Desligar a rede e confirmar continuidade local (automatizado).
- [ ] Repetir teste offline em computador físico do evento.
- [x] Restaurar um backup em segunda instalação temporária (automatizado).
- [ ] Repetir restauração em segundo computador físico do evento.
- [ ] Registrar incidentes, cliques desnecessários e trocas de tela.

## Critério para Próxima Iteração

Priorizar somente gargalos observados no piloto presencial ou operações
automatizadas marcadas como `REVISAR`.
