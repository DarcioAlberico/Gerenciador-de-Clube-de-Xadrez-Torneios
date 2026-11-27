# Guia: formulários de inscrição no Google Forms (REG-01)

O Albericus oferece três caminhos para a inscrição online. Escolha o que
preferir:

| Caminho | O que faz | Configuração |
|---|---|---|
| **Link pré-preenchido** (mais simples) | Você já tem um formulário; o sistema gera/compartilha o link com o **nome do torneio preenchido** para enviar aos jogadores | Nenhuma instalação; só colar 1x um link |
| **Gerar script (Apps Script)** | Cria o formulário padronizado 1x (sem digitar as perguntas), colando um script | Nenhuma instalação |
| **Criar ao vivo (API)** | O botão cria o formulário na sua conta e devolve o link | Projeto Google Cloud + OAuth (este guia, seção avançada) |

Para a maioria dos árbitros, **link pré-preenchido** já resolve. As duas
primeiras opções não exigem Google Cloud nem bibliotecas extras.

> **Vai distribuir o Albericus para a comunidade?** O usuário final **nunca**
> precisa criar projeto/credencial no Google Cloud. Para oferecer o "Entrar com
> o Google" (criar ao vivo) a todos, veja
> `docs/DISTRIBUICAO_E_VERIFICACAO_GOOGLE.md` (credencial embarcada + verificação
> do app). Sem isso, a comunidade já usa link pré-preenchido e script sem
> nenhuma configuração.

---

## Opção mais simples: link pré-preenchido (sem Google Cloud)

A ideia: o formulário existe uma vez (criado manualmente ou pela opção "Gerar
script"); o Albericus só monta o link com o **nome do torneio já preenchido** e
deixa os campos do jogador em branco para ele preencher.

1. Abra seu formulário no **Google Forms** (ou crie um com a opção "Gerar
   formulário (Google Forms)" do Albericus, que cola um script pronto).
2. No formulário, clique no menu **(três pontos) > Receber link preenchido
   automaticamente**.
3. Preencha **apenas o campo do torneio** com um valor de exemplo (ex.: `Copa
   Exemplo`) e clique em **Receber link**.
4. Copie o link gerado.
5. No Albericus: **Jogadores > Configurar formulário (link)**. Cole o link,
   clique em **Analisar**, escolha na lista o campo do torneio
   (`entry.XXXX = Copa Exemplo`) e clique em **Salvar**.
6. Pronto. Sempre que quiser, clique em **Compartilhar inscrição (link)**: o
   Albericus monta o link com o nome do torneio atual já preenchido, e você pode
   **copiar** para enviar aos jogadores ou **abrir no navegador** para conferir.

> Garanta, nas configurações do formulário, que **não exige login** para
> responder (desligue "Limitar a 1 resposta"/"coletar e-mail" se quiser que
> qualquer pessoa com o link se inscreva).

Para trazer as inscrições: no Google Forms, vincule as respostas a uma planilha,
baixe como CSV e use **Importar link Forms/Sheets** (ou **Importar com
mapeamento**, se mexeu nas colunas).

---

## Opção avançada: criar o formulário ao vivo pela API

Esta seção habilita o botão **Gerar formulário (Google Forms)** a criar o
formulário **ao vivo** na sua conta Google e devolver o link de inscrição.
Enquanto não estiver configurado, esse botão cai no modo de script (Apps
Script). A configuração e feita **uma única vez**, leva cerca de 10 minutos e
exige internet apenas no momento de criar cada formulário.

## Resumo do que você vai obter

- um arquivo `client_secret.json` (credencial OAuth de "App de computador");
- ele colocado na pasta de configuração do Albericus;
- na primeira criação, uma tela do Google pedindo autorização (login + permitir).

## Passo 1 - Instalar as bibliotecas

No ambiente do Albericus:

```
pip install google-api-python-client google-auth-oauthlib
```

(Já estão listadas no `requirements.txt`.)

## Passo 2 - Criar um projeto no Google Cloud

1. Acesse <https://console.cloud.google.com/>.
2. No topo, clique no seletor de projetos e em **Novo projeto**.
3. De um nome (ex.: `Albericus Forms`) e clique em **Criar**.

## Passo 3 - Habilitar a API do Google Forms

1. Com o projeto selecionado, acesse
   <https://console.cloud.google.com/apis/library/forms.googleapis.com>.
2. Clique em **Ativar**.

## Passo 4 - Configurar a tela de consentimento OAuth

1. Acesse **APIs e serviços > Tela de permissão OAuth**.
2. Tipo de usuário: **Externo** > **Criar**.
3. Preencha nome do app (ex.: `Albericus`), e-mail de suporte e e-mail do
   desenvolvedor. Pode pular os campos opcionais.
4. Em **Usuários de teste**, adicione o **seu próprio e-mail** Google (o mesmo
   que vai criar os formulários). Sem isso, o login será bloqueado.
5. Salve. Pode deixar o app em modo **Teste** (não precisa publicar).

> Em modo Teste, na primeira autorização o Google mostra um aviso de "app não
> verificado". Clique em **Avançado > Acessar (nome do app)** para continuar.
> Isso e normal para uso próprio.

## Passo 5 - Criar a credencial OAuth (App de computador)

1. Acesse **APIs e serviços > Credenciais**.
2. **Criar credenciais > ID do cliente OAuth**.
3. Tipo de aplicativo: **App de computador** (Desktop app).
4. De um nome e clique em **Criar**.
5. Clique em **Fazer o download do JSON**.

## Passo 6 - Colocar a credencial no lugar certo

Renomeie o arquivo baixado para `google_client_secret.json` e coloque em:

- **Windows:** `%LOCALAPPDATA%\Albericus\config\google_client_secret.json`
- **macOS:** `~/Library/Application Support/Albericus/config/google_client_secret.json`
- **Linux:** `~/.local/share/Albericus/config/google_client_secret.json`

A pasta `config` e criada automaticamente pelo Albericus na primeira execução.

> Alternativa: se preferir guardar o arquivo em outro lugar, defina o caminho
> completo na configuração `google_oauth_client_secret_path` (em
> `app_settings`).

## Passo 7 - Usar

1. Abra **Jogadores** no torneio e clique em **Gerar formulário (Google Forms)**.
2. Na primeira vez, o navegador abre pedindo login e autorização (Passo 4).
3. O Albericus cria o formulário e mostra:
   - **link para jogadores** (envie esse);
   - **link de edição** (para você ajustar, se quiser).
4. No Google Forms, abra **Respostas** e vincule a uma planilha.
5. Quando quiser trazer as inscrições, baixe a planilha como CSV e use
   **Importar link Forms/Sheets** (ou **Importar com mapeamento**, se mexeu nas
   colunas).

O token de acesso fica salvo em `config/google_forms_token.json`; nas próximas
vezes não será necessário logar de novo (até o token expirar/ser revogado).

## Segurança

- `client_secret.json` e `google_forms_token.json` são pessoais: não versione
  nem compartilhe.
- Para revogar o acesso, apague `google_forms_token.json` ou remova o app em
  <https://myaccount.google.com/permissions>.
