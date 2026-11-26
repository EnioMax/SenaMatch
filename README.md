# SenaMatch

O repositório tem duas partes: o programa que gera os jogos e o site que vende os lotes.

| Pasta | O que é | Tecnologia | Como rodar |
|---|---|---|---|
| [`streamlit/`](streamlit) | **Programa**: gerador e conferidor de jogos (núcleo de cálculo, integração com a Caixa, interface) | Python, NumPy, Streamlit | `cd streamlit && SENAMATCH_SECRET=... streamlit run app.py` |
| [`site/`](site) | **Site**: landing de captação, página do lote e painel do gestor (protótipo) | HTML, JS, Tailwind (CDN) | `npx wrangler pages dev` (com a função de leads) ou `python3 -m http.server -d site` (só páginas) |
| [`functions/`](functions) | **Função de leads** (`POST /api/leads`): grava o lead como cartão no Trello | Cloudflare Pages Functions | `npm test` |
| [`tools/`](tools) | Gerador dos lotes de demonstração do site | Python (usa `streamlit/nucleo.py`) | `streamlit/.venv/bin/python tools/gerar_lotes_demo.py` |
| [`docs/`](docs) | Regras de negócio e checklist de desenvolvimento | Markdown | |

## Programa (`streamlit/`)

- Variáveis de ambiente: `SENAMATCH_SECRET` (obrigatória; também aceita `st.secrets`) e `SENAMATCH_DEV=1` (só desenvolvimento, usa um segredo fictício).
- Testes: `cd streamlit && python3 test_nucleo.py` (ou `pytest`).
- O CI em `.github/workflows/ci.yml` cobre apenas esta parte.

## Site (`site/`)

- O lote é de **5 jogos**, como no programa. A página do lote (`/meu-lote`) e o painel leem [`site/data/lotes_demo.js`](site/data/lotes_demo.js), gerado pelo núcleo com um **segredo fictício**: são jogos de demonstração, não os da venda. Regere com `tools/gerar_lotes_demo.py`.
- O painel do gestor guarda dados no `localStorage` do navegador, sem autenticação: não use com dados reais.
- Os resultados da página do lote são **oficiais**, vindos da API da Caixa por `/api/sorteios` (com cache de 10 min). O painel ainda usa concursos fictícios.

### Exclusão de jogos e catálogo de venda (regras v5)

São excluídos jogos com as 6 dezenas pares, as 6 ímpares, 4 ou mais dezenas consecutivas, ou mais de 3 dezenas em qualquer faixa de dezena (01–10, 11–20, 21–30, 31–40, 41–50 ou 51–60). Também são excluídos os jogos cuja **soma das 6 dezenas** fique fora de **150 a 216** (limites incluídos). O núcleo ([`streamlit/nucleo.py`](streamlit/nucleo.py)) mantém o conjunto completo (`gerar_lotes`) e forma o **catálogo de venda** (`criar_catalogo` → `Catalogo`): os jogos aprovados, na ordem do conjunto completo, agrupados de 5 em 5, com numeração própria. Com as âncoras do cliente são 17.119.202 jogos excluídos, 20.882.398 aprovados e **4.176.479 lotes** (22 arquivos CSV, 5 ZIPs); os últimos 3 jogos aprovados ficam sem lote. As contagens por motivo podem se sobrepor. O catálogo guarda só 1 bit por jogo (~5 MB).

- O app (tela de lotes, arquivos CSV/ZIP, conferidor e simulador) usa o catálogo. O painel **Jogos excluídos do catálogo** mostra os totais por regra.
- Como os jogos excluídos saem, as dezenas deixam de aparecer exatamente o mesmo número de vezes: a soma tira mais jogos com dezenas extremas (a dezena 01 aparece ~9% e a 60 ~6% abaixo da média; a 28 ~5% acima), e a mais frequente aparece ~18% mais que a menos frequente.
- O catálogo demo do site é formado por esse catálogo (`tools/gerar_lotes_demo.py`).
- Isso não aumenta a chance de ganhar. A v5 altera a numeração e a composição dos lotes em relação à v4 (e à v3); não substitua a versão de um catálogo já vendido. Versão das regras em `REGRAS_VERSAO`.

### Catálogo filtrado experimental

[`streamlit/catalogo_filtrado.py`](streamlit/catalogo_filtrado.py) permite testar, isoladamente, a reorganização de jogos em lotes de cinco após excluir jogos com cinco ou mais dezenas da mesma paridade, quatro ou mais consecutivas ou progressão aritmética. `criar_catalogo(ancoras, semente)` percorre o catálogo original e constrói um índice em memória; `gerar_lotes` usa índices de lotes experimentais começando em zero. Se houver jogos aprovados sobrando, a criação falha explicitamente.

No app Streamlit, abra **Catálogo filtrado experimental**, cole os 30 pares no formato `N1: 07, 12; N2: 11, 27; ...` e clique em **Gerar catálogo experimental**. A construção percorre todos os jogos e pode levar alguns minutos e consumir bastante memória; o índice fica apenas na sessão. Os lotes usam um segredo fictício e uma numeração separada. Alterar o texto descarta o catálogo da sessão; também é possível liberá-lo pelo botão.

Esta área não altera as âncoras padrão nem está conectada ao site ou às vendas. O filtro não garante equilíbrio igual entre dezenas nem aumenta a chance de uma combinação. Antes de usá-lo em produção, é necessário versionar e preservar a configuração, criar armazenamento e alocação segura e validar desempenho e regras de negócio.

### Leads no Trello

O formulário da landing envia para `/api/leads` ([`functions/api/leads.js`](functions/api/leads.js)). Configure como secrets da Cloudflare Pages (ou em `.dev.vars` localmente, a partir de [`.dev.vars.example`](.dev.vars.example)):

- `TRELLO_KEY`, `TRELLO_TOKEN`, `TRELLO_LIST_ID` (obrigatórios) e `ALLOWED_ORIGIN` (opcional).
- Para aceitar ambos os domínios do site, configure `ALLOWED_ORIGIN` como `https://senamatch.pages.dev,https://senamatch.com.br` (origens exatas separadas por vírgula). Publique primeiro o código que aceita a lista, atualize a variável e refaça o deploy. Sem `ALLOWED_ORIGIN`, a checagem de origem fica desativada.
- `WHATSAPP_NUMERO` (DDD + número, só dígitos): usado por `/go/whatsapp` ([`functions/go/whatsapp.js`](functions/go/whatsapp.js)) para os botões de WhatsApp, sem expor o número no repositório.
- `ADMIN_PASSWORD`: senha do painel (`/admin`), exigida por Basic Auth em [`functions/_middleware.js`](functions/_middleware.js) (qualquer usuário). Sem ela, o painel fica bloqueado (503).
- Nunca coloque chave ou token no HTML nem no repositório.
- Campanhas: use links de anúncio como `https://senamatch.com.br/?utm_source=instagram&utm_medium=cpc&utm_campaign=nome-da-campanha`. A landing envia os três valores com o lead e o cartão do Trello mostra `**UTM:** source=… · medium=… · campaign=…`. Os valores são normalizados (minúsculas, só letras, dígitos, `.`, `-`, `_`, `+` e espaço, até 60 caracteres).
- Publicação: Cloudflare Pages com diretório de saída `site` (ver [`wrangler.toml`](wrangler.toml)).

Passo a passo completo: [`docs/CHECKLIST_DESENVOLVIMENTO.md`](docs/CHECKLIST_DESENVOLVIMENTO.md). Regras de negócio: [`docs/REGRAS_DE_NEGOCIO.md`](docs/REGRAS_DE_NEGOCIO.md).

### Teste local de confirmação

Execute `npm run test:confirmacao-demo` na raiz do projeto. O teste simula cadastro, confirmação, expiração, reenvio e entrega de cinco jogos do catálogo fictício, tudo em memória. Não envia e-mail, não acessa o Trello nem altera o site. O link `example.invalid` não é acessível pelo navegador. Isso é apenas uma simulação automatizada, não uma implementação de confirmação ou de acesso seguro para produção.
