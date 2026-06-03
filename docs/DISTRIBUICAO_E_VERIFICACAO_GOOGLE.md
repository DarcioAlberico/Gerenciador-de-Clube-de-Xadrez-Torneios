# Distribuir o Albericus para a comunidade — formularios de inscricao

Este documento e para **quem empacota e distribui** o Albericus (desenvolvedor),
nao para o arbitro final. Explica como oferecer a inscricao online para toda a
comunidade e o plano recomendado.

## Plano recomendado (combinado): opcao 1 agora + opcao 2 em paralelo

- **Agora (sem fricção, sem limite):** o caminho padrao da comunidade e o
  **link pre-preenchido** + **gerador de script Apps Script**. Nao exigem
  projeto no Google Cloud, nao tem teto de usuarios e cada arbitro usa a propria
  conta. Ja funcionam na distribuicao atual, sem nenhuma configuracao extra.
- **Em paralelo (login para todos):** preparar a **opcao 2** — app verificado +
  credencial OAuth embarcada — para que o usuario so clique em "Entrar com o
  Google". Quando a verificacao do Google sair, o "login para todos" liga sem
  mudar nada para o usuario final.

O importante: **o usuario final nunca cria projeto/credencial no Google Cloud**.
Isso e trabalho unico do desenvolvedor.

## Parte 1 — Credencial embarcada (codigo ja pronto)

O `GoogleFormsService` procura a credencial OAuth nesta ordem:

1. caminho explicito em `app_settings.google_oauth_client_secret_path`;
2. credencial do **proprio usuario** em
   `%LOCALAPPDATA%\Albericus\config\google_client_secret.json`;
3. credencial **embarcada na distribuicao**: `assets/google_client_secret.json`.

Para distribuir com "Entrar com o Google" para todos:

1. Crie/baixe a credencial OAuth do **app verificado** (tipo "App para
   computador"), conforme `docs/GUIA_GOOGLE_FORMS.md`.
2. Coloque o arquivo em **`assets/google_client_secret.json`** antes de buildar.
   O `albericus.spec` empacota a pasta `assets/` inteira (`datas=[("assets",
   "assets")]`), entao o arquivo vai junto automaticamente.
3. Builde normalmente (`build.bat` / `scripts/build_windows.ps1`).

Observacoes:

- O arquivo `**/google_client_secret.json` esta no `.gitignore`: **nunca
  comite** uma credencial real.
- Credenciais de "App para computador" **nao sao tratadas como segredo
  confidencial** pelo Google (e um "installed app"); embarcar e aceitavel.
- Cada usuario autentica na **propria conta**; o token fica na maquina dele
  (`config/google_forms_token.json`). Voce nao acessa os dados deles.
- Se um usuario configurar a propria credencial (passos 1-2 da ordem acima), ela
  tem prioridade sobre a embarcada.

## Parte 2 — Verificacao do app no Google (uma vez)

Enquanto o app **nao** estiver verificado, para qualquer usuario externo:

- aparece o aviso **"app nao verificado"** (da para prosseguir em *Avancado →
  Acessar*);
- ha **teto de ~100 usuarios** que podem autorizar.

O escopo usado e `https://www.googleapis.com/auth/forms.body`, classificado como
**sensivel** (nao "restrito"). Logo, exige a **verificacao padrao**, mas **nao**
a auditoria de seguranca paga (CASA) — essa e so para escopos restritos
(Gmail/Drive amplos). Confirme a classificacao atual na pagina de escopos do
Google, pois as politicas mudam.

Checklist da verificacao:

1. **Tela de consentimento OAuth** → publicar o app em **Producao**
   (Publico-alvo → Publicar app).
2. Preencher **nome do app, logo, e-mail de suporte e e-mail do desenvolvedor**.
3. Informar **dominio autorizado**, **pagina inicial (homepage)** e **URL da
   politica de privacidade** (precisam estar publicados publicamente).
4. **Justificar o escopo** `forms.body` (por que o app cria/edita formularios
   em nome do usuario).
5. Pode ser exigido um **video de demonstracao** mostrando o fluxo de login e o
   uso do escopo.
6. **Enviar para verificacao** e responder aos pedidos do revisor do Google
   (pode levar de dias a algumas semanas).

> Dica: hospede a politica de privacidade e a homepage de graca (por exemplo,
> GitHub Pages). Use o modelo abaixo como ponto de partida.

## Modelo de Politica de Privacidade

> Ajuste os campos entre colchetes e publique numa URL publica.

```
Politica de Privacidade - Albericus

Ultima atualizacao: [DATA]

O Albericus e um aplicativo de gestao de torneios de xadrez. Esta politica
descreve como o recurso de criacao de formularios de inscricao no Google Forms
trata os dados.

1. Acesso solicitado
   O app solicita permissao para criar e editar formularios do Google Forms
   (escopo forms.body) na conta Google do proprio usuario, apenas para gerar o
   formulario de inscricao do torneio.

2. Uso dos dados
   O formulario e criado na conta Google do usuario. As respostas dos jogadores
   ficam na conta do usuario (no Google Forms/Sheets dele). O desenvolvedor do
   Albericus nao coleta, armazena nem acessa esses dados.

3. Armazenamento local
   O token de acesso do Google fica salvo apenas no computador do usuario e pode
   ser revogado a qualquer momento, apagando o arquivo de token ou em
   https://myaccount.google.com/permissions.

4. Compartilhamento
   Nenhum dado e compartilhado com terceiros.

5. Contato
   [SEU NOME] - [SEU E-MAIL]
```

## Resumo

| Item | Quem faz | Quando |
|---|---|---|
| Link pre-preenchido / script (sem OAuth) | Arbitro (uso normal) | Ja disponivel |
| Embarcar `assets/google_client_secret.json` | Desenvolvedor | Antes de buildar (opcao 2) |
| Verificar o app no Google | Desenvolvedor | Uma vez (em paralelo) |
| Entrar com a propria conta Google | Cada usuario | No 1o uso do modo ao vivo |
