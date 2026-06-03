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

## Politica de privacidade pronta

Ja existe uma pagina pronta em `docs/politica_privacidade.html` (preenchida com
o responsavel, o contato e a descricao correta do uso do escopo). Confira o
nome/contato e publique-a numa URL publica.

Publicar de graca via GitHub Pages (sugestao):

1. No repositorio, **Settings > Pages**.
2. Em **Build and deployment**, fonte **Deploy from a branch**.
3. Branch `main`, pasta `/docs` > **Save**.
4. A pagina ficara em
   `https://darcioalberico.github.io/Gerenciador-de-Clube-de-Xadrez-Torneios/politica_privacidade.html`.
5. Use essa URL como **Politica de privacidade** na verificacao, e a pagina do
   repositorio como **Pagina inicial (homepage)**.

## Justificativa do escopo OAuth (para o formulario de verificacao)

O Google pede que voce explique, em ingles, por que o app usa o escopo. Cole o
texto abaixo (ajuste se quiser):

> **EN —** Albericus is an offline-first desktop application for managing chess
> tournaments, used by arbiters and clubs. It uses the Google Forms API scope
> `https://www.googleapis.com/auth/forms.body` solely to let the arbiter create,
> in their **own** Google account and with a single click, a standardized
> tournament registration form, and to read back that form's responder URL so it
> can be shared with players. The application does not read the user's other
> forms and does not access Drive, Gmail, Calendar, Contacts or any other data.
> We request `forms.body` because creating the form's questions requires the
> `forms.batchUpdate` write operation, and no narrower scope exists for creating
> form items. The app has **no backend server**: no user data is sent to us; the
> OAuth token is stored only on the user's local machine, and all forms and
> responses remain in the user's own Google account. Usage complies with the
> Google API Services User Data Policy, including Limited Use.

> **PT (referencia) —** O Albericus e um aplicativo desktop offline-first de
> gestao de torneios de xadrez. Usa o escopo `forms.body` apenas para o arbitro
> criar, na propria conta e com um clique, um formulario de inscricao
> padronizado, e ler o link de resposta para compartilhar com os jogadores. Nao
> le outros formularios nem acessa Drive/Gmail/Agenda/Contatos. O escopo
> `forms.body` e necessario porque criar as perguntas exige a escrita via
> `batchUpdate`. O app nao tem servidor: nenhum dado e enviado ao desenvolvedor;
> o token fica so na maquina do usuario e os dados ficam na conta Google dele.

### Dicas para a revisao
- Publique a politica de privacidade e a homepage **antes** de enviar.
- Garanta que o e-mail de suporte e o e-mail do desenvolvedor estao corretos na
  tela de consentimento.
- Se pedirem **video de demonstracao**, grave a tela mostrando: abrir o
  Albericus, clicar em "Gerar formulario (Google Forms)", o login "Entrar com o
  Google", a tela de consentimento com o escopo, e o formulario criado.
- Como o escopo e **sensivel** (nao restrito), nao e exigida a auditoria de
  seguranca independente (CASA).
