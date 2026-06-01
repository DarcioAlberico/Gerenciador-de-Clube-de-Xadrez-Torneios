# Piloto Operacional Simulado

Gerado em: 2026-06-01T01:59:28-03:00

Este relatorio executa o fluxo critico do arbitro em banco temporario.
Ele detecta regressoes locais de desempenho, mas nao substitui o teste
presencial com operadores, impressora e rede do evento.

## Resultado Automatizado

### Cenario com 121 jogadores

Status geral: **OK**

Mesas validas na primeira rodada: 60

| Operacao | Tempo | Limite | Status | Detalhes |
|---|---:|---:|---|---|
| Cadastrar inscritos | 570.6269 ms | 10000 ms | OK |  |
| Pre-visualizar primeira rodada | 14.2775 ms | 1000 ms | OK | 61 emparceiramentos planejados |
| Gerar primeira rodada | 75.3746 ms | 2000 ms | OK |  |
| Carregar painel do arbitro | 14.2522 ms | 500 ms | OK | 60 pendentes; 50 exibidos inline |
| Exportar lista de chamada PDF | 51.0615 ms | 5000 ms | OK | 4 paginas |
| Exportar sumulas PDF | 67.3316 ms | 5000 ms | OK | 60 paginas |
| Exportar mural PDF com QR | 602.9565 ms | 30000 ms | OK | 5 paginas |
| Lancar resultado e recarregar painel | 39.4836 ms | 250 ms | OK | media de 20 lancamentos |
| Fechar primeira rodada | 106.4533 ms | 5000 ms | OK |  |
| Calcular tabela cruzada | 9.0266 ms | 2000 ms | OK | 121 linhas |
| Exportar tabela cruzada HTML | 10.7942 ms | 2000 ms | OK | 15123 bytes |
| Criar backup final | 12.9309 ms | 5000 ms | OK | 1454080 bytes |
| Restaurar backup em segunda instalacao | 622.2023 ms | 5000 ms | OK | 1 rodada; 61 mesas validadas |
| Validar continuidade offline | 866.7484 ms | 5000 ms | OK | painel, 4 resultados, fechamento, classificacao, exportacoes e backup validados |
| Simular envios QR simultaneos e aprovar | 3099.6495 ms | 5000 ms | OK | 20 envios concorrentes recebidos e aprovados |
| Cadastrar inscricao de ultima hora e atualizar previa | 45.1981 ms | 2000 ms | OK | 122 inscritos; 0,5 ponto; historico preservado; jogador presente na previa seguinte |
| Importar base oficial FIDE local | 29.4552 ms | 5000 ms | OK | 121 registros oficiais importados |
| Comparar ratings oficiais antes da rodada 1 | 139.2976 ms | 2000 ms | OK | 121 alteracoes; 0 sem correspondencia; sem persistir |
| Confirmar correcoes oficiais selecionadas | 700.3101 ms | 10000 ms | OK | 121 alteracoes aplicadas seletivamente |
| Localizar mesa e lancar resultado pelo painel | 48.8176 ms | 1000 ms | OK | mesa 60 localizada fora do recorte inline, lancada e removida das pendencias |

### Cenario com 801 jogadores

Status geral: **OK**

Mesas validas na primeira rodada: 400

| Operacao | Tempo | Limite | Status | Detalhes |
|---|---:|---:|---|---|
| Cadastrar inscritos | 3918.2690 ms | 10000 ms | OK |  |
| Pre-visualizar primeira rodada | 29.9748 ms | 1000 ms | OK | 401 emparceiramentos planejados |
| Gerar primeira rodada | 86.0819 ms | 2000 ms | OK |  |
| Carregar painel do arbitro | 23.0215 ms | 500 ms | OK | 400 pendentes; 50 exibidos inline |
| Exportar lista de chamada PDF | 67.8427 ms | 5000 ms | OK | 22 paginas |
| Exportar sumulas PDF | 419.1881 ms | 5000 ms | OK | 400 paginas |
| Exportar mural PDF com QR | 3701.6010 ms | 30000 ms | OK | 27 paginas |
| Lancar resultado e recarregar painel | 49.4234 ms | 250 ms | OK | media de 20 lancamentos |
| Fechar primeira rodada | 192.0668 ms | 5000 ms | OK |  |
| Calcular tabela cruzada | 23.9210 ms | 2000 ms | OK | 801 linhas |
| Exportar tabela cruzada HTML | 25.5569 ms | 2000 ms | OK | 96042 bytes |
| Criar backup final | 19.6087 ms | 5000 ms | OK | 4890624 bytes |
| Restaurar backup em segunda instalacao | 699.9135 ms | 5000 ms | OK | 1 rodada; 401 mesas validadas |
| Validar continuidade offline | 860.8958 ms | 5000 ms | OK | painel, 4 resultados, fechamento, classificacao, exportacoes e backup validados |
| Simular envios QR simultaneos e aprovar | 2846.3054 ms | 5000 ms | OK | 20 envios concorrentes recebidos e aprovados |
| Cadastrar inscricao de ultima hora e atualizar previa | 117.0289 ms | 2000 ms | OK | 802 inscritos; 0,5 ponto; historico preservado; jogador presente na previa seguinte |
| Importar base oficial FIDE local | 146.0958 ms | 5000 ms | OK | 700 registros oficiais importados |
| Comparar ratings oficiais antes da rodada 1 | 882.3479 ms | 2000 ms | OK | 700 alteracoes; 101 sem correspondencia; sem persistir |
| Confirmar correcoes oficiais selecionadas | 4325.6951 ms | 10000 ms | OK | 700 alteracoes aplicadas seletivamente |
| Localizar mesa e lancar resultado pelo painel | 73.5168 ms | 1000 ms | OK | mesa 400 localizada fora do recorte inline, lancada e removida das pendencias |

## Validacao Presencial Pendente

Execute ao menos um ensaio com arbitro e auxiliar usando o
[manual operacional](Manual_Operacional_Arbitragem.pdf).

- [x] Cronometrar inscricao de ultima hora (automatizado).
- [ ] Repetir inscricao de ultima hora com operador no computador do evento.
- [x] Cronometrar correcao de rating oficial antes da rodada 1 (automatizado).
- [ ] Repetir correcao de rating oficial com operador antes do evento.
- [ ] Confirmar legibilidade do mural impresso a distancia.
- [ ] Testar impressao de sumulas e cartoes na impressora do evento.
- [x] Medir tempo para localizar e lancar resultado de uma mesa (automatizado).
- [ ] Repetir localizacao e lancamento de mesa com arbitro no evento.
- [x] Simular envio QR simultaneo e aprovacao pelo arbitro (automatizado).
- [ ] Repetir envio QR simultaneo com celulares na rede local do evento.
- [x] Desligar a rede e confirmar continuidade local (automatizado).
- [ ] Repetir teste offline em computador fisico do evento.
- [x] Restaurar um backup em segunda instalacao temporaria (automatizado).
- [ ] Repetir restauracao em segundo computador fisico do evento.
- [ ] Registrar incidentes, cliques desnecessarios e trocas de tela.

## Criterio para Proxima Iteracao

Priorizar somente gargalos observados no piloto presencial ou operacoes
automatizadas marcadas como `REVISAR`.
