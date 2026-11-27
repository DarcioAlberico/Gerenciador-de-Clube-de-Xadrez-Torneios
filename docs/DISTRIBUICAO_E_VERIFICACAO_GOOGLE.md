# Distribuir o Albericus para a comunidade — formulários de inscrição

Este documento e para **quem empacota e distribui** o Albericus (desenvolvedor),
não para o árbitro final. Explica como oferecer a inscrição online para toda a
comunidade e o plano recomendado.

## Plano recomendado (combinado): opção 1 agora + opção 2 em paralelo

- **Agora (sem fricção, sem limite):** o caminho padrão da comunidade e o
  **link pré-preenchido** + **gerador de script Apps Script**. Não exigem
  projeto no Google Cloud, não tem teto de usuários e cada árbitro usa a própria
  conta. Já funcionam na distribuição atual, sem nenhuma configuração extra.
- **Em paralelo (login para todos):** preparar a **opção 2** — app verificado +
  credencial OAuth embarcada — para que o usuário só clique em "Entrar com o
  Google". Quando a verificação do Google sair, o "login para todos" liga sem
  mudar nada para o usuário final.

O importante: **o usuário final nunca cria projeto/credencial no Google Cloud**.
Isso e trabalho único do desenvolvedor.

## Parte 1 — Credencial embarcada (código já pronto)

O `GoogleFormsService` procura a credencial OAuth nesta ordem:

1. caminho explicito em `app_settings.google_oauth_client_secret_path`;
2. credencial do **próprio usuário** em
   `%LOCALAPPDATA%\Albericus\config\google_client_secret.json`;
3. credencial **embarcada na distribuição**: `assets/google_client_secret.json`.

Para distribuir com "Entrar com o Google" para todos:

1. Crie/baixe a credencial OAuth do **app verificado** (tipo "App para
   computador"), conforme `docs/GUIA_GOOGLE_FORMS.md`.
2. Coloque o arquivo em **`assets/google_client_secret.json`** antes de buildar.
   O `albericus.spec` empacota a pasta `assets/` inteira (`datas=[("assets",
   "assets")]`), então o arquivo vai junto automaticamente.
3. Builde normalmente (`build.bat` / `scripts/build_windows.ps1`).

Observações:

- O arquivo `**/google_client_secret.json` está no `.gitignore`: **nunca
  comitê** uma credencial real.
- Credenciais de "App para computador" **não são tratadas como segredo
  confidencial** pelo Google (e um "installed app"); embarcar e aceitável.
- Cada usuário autentica na **própria conta**; o token fica na maquina dele
  (`config/google_forms_token.json`). Você não acessa os dados deles.
- Se um usuário configurar a própria credencial (passos 1-2 da ordem acima), ela
  tem prioridade sobre a embarcada.

## Parte 2 — Verificação do app no Google (uma vez)

Enquanto o app **não** estiver verificado, para qualquer usuário externo:

- aparece o aviso **"app não verificado"** (da para prosseguir em *Avançado →
  Acessar*);
- há **teto de ~100 usuários** que podem autorizar.

O escopo usado e `https://www.googleapis.com/auth/forms.body`, classificado como
**sensível** (não "restrito"). Logo, exige a **verificação padrão**, mas **não**
a auditoria de segurança paga (CASA) — essa e só para escopos restritos
(Gmail/Drive amplos). Confirme a classificação atual na página de escopos do
Google, pois as políticas mudam.

Checklist da verificação:

1. **Tela de consentimento OAuth** → publicar o app em **Produção**
   (Público-alvo → Publicar app).
2. Preencher **nome do app, logo, e-mail de suporte e e-mail do desenvolvedor**.
3. Informar **domínio autorizado**, **página inicial (homepage)** e **URL da
   política de privacidade** (precisam estar publicados publicamente).
4. **Justificar o escopo** `forms.body` (por que o app cria/edita formulários
   em nome do usuário).
5. Pode ser exigido um **vídeo de demonstração** mostrando o fluxo de login e o
   uso do escopo.
6. **Enviar para verificação** e responder aos pedidos do revisor do Google
   (pode levar de dias a algumas semanas).

> Dica: hospede a política de privacidade e a homepage de graça (por exemplo,
> GitHub Pages). Use o modelo abaixo como ponto de partida.

## Modelo de Política de Privacidade

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
| Link pré-preenchido / script (sem OAuth) | Árbitro (uso normal) | Já disponível |
| Embarcar `assets/google_client_secret.json` | Desenvolvedor | Antes de buildar (opção 2) |
| Verificar o app no Google | Desenvolvedor | Uma vez (em paralelo) |
| Entrar com a própria conta Google | Cada usuário | No 1o uso do modo ao vivo |

## Política de privacidade pronta

Já existe uma página pronta em `docs/politica_privacidade.html` (preenchida com
o responsável, o contato e a descrição correta do uso do escopo). Confira o
nome/contato e publique-a numa URL publica.

Publicar de graça via GitHub Pages (sugestão):

1. No repositório, **Settings > Pages**.
2. Em **Build and deployment**, fonte **Deploy from a branch**.
3. Branch `main`, pasta `/docs` > **Save**.
4. A página ficara em
   `https://darcioalberico.github.io/Gerenciador-de-Clube-de-Xadrez-Torneios/politica_privacidade.html`.
5. Use essa URL como **Política de privacidade** na verificação, e a página do
   repositório como **Página inicial (homepage)**.

## Justificativa do escopo OAuth (para o formulário de verificação)

O Google pede que você explique, em inglês, por que o app usa o escopo. Cole o
texto abaixo (ajuste se quiser):

> **EN —** Albericus is an offline-first desktop application for managing chess
> tournaments, used by arbiters and clubs. It uses the Google Forms API scope
> `https://www.googleapis.com/auth/forms.body` solely to let the arbiter create,
> in their **own** Google account and with a single click, a standardized
> tournament registration form, and to read back that form's responder URL só it
> can be shared with players. The application does not read the user's other
> forms and does not access Drive, Gmail, Calendar, Contacts or any other data.
> We request `forms.body` because creating the form's questions requires the
> `forms.batchUpdate` write operation, and no narrower scope exists for creating
> form items. The app has **no backend server**: no user data is sent to us; the
> OAuth token is stored only on the user's local machine, and all forms and
> responses remain in the user's own Google account. Usage complies with the
> Google API Services User Data Policy, including Limited Use.

> **PT (referência) —** O Albericus e um aplicativo desktop offline-first de
> gestão de torneios de xadrez. Usa o escopo `forms.body` apenas para o árbitro
> criar, na própria conta e com um clique, um formulário de inscrição
> padronizado, e ler o link de resposta para compartilhar com os jogadores. Não
> lê outros formulários nem acessa Drive/Gmail/Agenda/Contatos. O escopo
> `forms.body` é necessário porque criar as perguntas exige a escrita via
> `batchUpdate`. O app não tem servidor: nenhum dado e enviado ao desenvolvedor;
> o token fica só na maquina do usuário e os dados ficam na conta Google dele.

### Dicas para a revisão
- Publique a política de privacidade e a homepage **antes** de enviar.
- Garanta que o e-mail de suporte e o e-mail do desenvolvedor estão corretos na
  tela de consentimento.
- Se pedirem **vídeo de demonstração**, grave a tela mostrando: abrir o
  Albericus, clicar em "Gerar formulário (Google Forms)", o login "Entrar com o
  Google", a tela de consentimento com o escopo, e o formulário criado.
- Como o escopo e **sensível** (não restrito), não é exigida a auditoria de
  segurança independente (CASA).
