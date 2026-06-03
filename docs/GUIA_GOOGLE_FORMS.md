# Guia: formularios de inscricao no Google Forms (REG-01)

O Albericus oferece tres caminhos para a inscricao online. Escolha o que
preferir:

| Caminho | O que faz | Configuracao |
|---|---|---|
| **Link pre-preenchido** (mais simples) | Voce ja tem um formulario; o sistema gera/compartilha o link com o **nome do torneio preenchido** para enviar aos jogadores | Nenhuma instalacao; so colar 1x um link |
| **Gerar script (Apps Script)** | Cria o formulario padronizado 1x (sem digitar as perguntas), colando um script | Nenhuma instalacao |
| **Criar ao vivo (API)** | O botao cria o formulario na sua conta e devolve o link | Projeto Google Cloud + OAuth (este guia, secao avancada) |

Para a maioria dos arbitros, **link pre-preenchido** ja resolve. As duas
primeiras opcoes nao exigem Google Cloud nem bibliotecas extras.

> **Vai distribuir o Albericus para a comunidade?** O usuario final **nunca**
> precisa criar projeto/credencial no Google Cloud. Para oferecer o "Entrar com
> o Google" (criar ao vivo) a todos, veja
> `docs/DISTRIBUICAO_E_VERIFICACAO_GOOGLE.md` (credencial embarcada + verificacao
> do app). Sem isso, a comunidade ja usa link pre-preenchido e script sem
> nenhuma configuracao.

---

## Opcao mais simples: link pre-preenchido (sem Google Cloud)

A ideia: o formulario existe uma vez (criado manualmente ou pela opcao "Gerar
script"); o Albericus so monta o link com o **nome do torneio ja preenchido** e
deixa os campos do jogador em branco para ele preencher.

1. Abra seu formulario no **Google Forms** (ou crie um com a opcao "Gerar
   formulario (Google Forms)" do Albericus, que cola um script pronto).
2. No formulario, clique no menu **(tres pontos) > Receber link preenchido
   automaticamente**.
3. Preencha **apenas o campo do torneio** com um valor de exemplo (ex.: `Copa
   Exemplo`) e clique em **Receber link**.
4. Copie o link gerado.
5. No Albericus: **Jogadores > Configurar formulario (link)**. Cole o link,
   clique em **Analisar**, escolha na lista o campo do torneio
   (`entry.XXXX = Copa Exemplo`) e clique em **Salvar**.
6. Pronto. Sempre que quiser, clique em **Compartilhar inscricao (link)**: o
   Albericus monta o link com o nome do torneio atual ja preenchido, e voce pode
   **copiar** para enviar aos jogadores ou **abrir no navegador** para conferir.

> Garanta, nas configuracoes do formulario, que **nao exige login** para
> responder (desligue "Limitar a 1 resposta"/"coletar e-mail" se quiser que
> qualquer pessoa com o link se inscreva).

Para trazer as inscricoes: no Google Forms, vincule as respostas a uma planilha,
baixe como CSV e use **Importar link Forms/Sheets** (ou **Importar com
mapeamento**, se mexeu nas colunas).

---

## Opcao avancada: criar o formulario ao vivo pela API

Esta secao habilita o botao **Gerar formulario (Google Forms)** a criar o
formulario **ao vivo** na sua conta Google e devolver o link de inscricao.
Enquanto nao estiver configurado, esse botao cai no modo de script (Apps
Script). A configuracao e feita **uma unica vez**, leva cerca de 10 minutos e
exige internet apenas no momento de criar cada formulario.

## Resumo do que voce vai obter

- um arquivo `client_secret.json` (credencial OAuth de "App de computador");
- ele colocado na pasta de configuracao do Albericus;
- na primeira criacao, uma tela do Google pedindo autorizacao (login + permitir).

## Passo 1 - Instalar as bibliotecas

No ambiente do Albericus:

```
pip install google-api-python-client google-auth-oauthlib
```

(Ja estao listadas no `requirements.txt`.)

## Passo 2 - Criar um projeto no Google Cloud

1. Acesse <https://console.cloud.google.com/>.
2. No topo, clique no seletor de projetos e em **Novo projeto**.
3. De um nome (ex.: `Albericus Forms`) e clique em **Criar**.

## Passo 3 - Habilitar a API do Google Forms

1. Com o projeto selecionado, acesse
   <https://console.cloud.google.com/apis/library/forms.googleapis.com>.
2. Clique em **Ativar**.

## Passo 4 - Configurar a tela de consentimento OAuth

1. Acesse **APIs e servicos > Tela de permissao OAuth**.
2. Tipo de usuario: **Externo** > **Criar**.
3. Preencha nome do app (ex.: `Albericus`), e-mail de suporte e e-mail do
   desenvolvedor. Pode pular os campos opcionais.
4. Em **Usuarios de teste**, adicione o **seu proprio e-mail** Google (o mesmo
   que vai criar os formularios). Sem isso, o login sera bloqueado.
5. Salve. Pode deixar o app em modo **Teste** (nao precisa publicar).

> Em modo Teste, na primeira autorizacao o Google mostra um aviso de "app nao
> verificado". Clique em **Avancado > Acessar (nome do app)** para continuar.
> Isso e normal para uso proprio.

## Passo 5 - Criar a credencial OAuth (App de computador)

1. Acesse **APIs e servicos > Credenciais**.
2. **Criar credenciais > ID do cliente OAuth**.
3. Tipo de aplicativo: **App de computador** (Desktop app).
4. De um nome e clique em **Criar**.
5. Clique em **Fazer o download do JSON**.

## Passo 6 - Colocar a credencial no lugar certo

Renomeie o arquivo baixado para `google_client_secret.json` e coloque em:

- **Windows:** `%LOCALAPPDATA%\Albericus\config\google_client_secret.json`
- **macOS:** `~/Library/Application Support/Albericus/config/google_client_secret.json`
- **Linux:** `~/.local/share/Albericus/config/google_client_secret.json`

A pasta `config` e criada automaticamente pelo Albericus na primeira execucao.

> Alternativa: se preferir guardar o arquivo em outro lugar, defina o caminho
> completo na configuracao `google_oauth_client_secret_path` (em
> `app_settings`).

## Passo 7 - Usar

1. Abra **Jogadores** no torneio e clique em **Gerar formulario (Google Forms)**.
2. Na primeira vez, o navegador abre pedindo login e autorizacao (Passo 4).
3. O Albericus cria o formulario e mostra:
   - **link para jogadores** (envie esse);
   - **link de edicao** (para voce ajustar, se quiser).
4. No Google Forms, abra **Respostas** e vincule a uma planilha.
5. Quando quiser trazer as inscricoes, baixe a planilha como CSV e use
   **Importar link Forms/Sheets** (ou **Importar com mapeamento**, se mexeu nas
   colunas).

O token de acesso fica salvo em `config/google_forms_token.json`; nas proximas
vezes nao sera necessario logar de novo (ate o token expirar/ser revogado).

## Seguranca

- `client_secret.json` e `google_forms_token.json` sao pessoais: nao versione
  nem compartilhe.
- Para revogar o acesso, apague `google_forms_token.json` ou remova o app em
  <https://myaccount.google.com/permissions>.
