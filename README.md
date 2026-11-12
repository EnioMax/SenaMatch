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

- O lote é de **5 jogos**, como no programa (7.600.320 lotes). A página do lote (`/meu-lote`) e o painel leem [`site/data/lotes_demo.js`](site/data/lotes_demo.js), gerado pelo núcleo com um **segredo fictício**: são jogos de demonstração, não os da venda. Regere com `tools/gerar_lotes_demo.py`.
- O painel do gestor guarda dados no `localStorage` do navegador, sem autenticação: não use com dados reais.
- Os resultados da página do lote são **oficiais**, vindos da API da Caixa por `/api/sorteios` (com cache de 10 min). O painel ainda usa concursos fictícios.

### Exclusão de jogos e catálogo de venda (regras v3)

O cliente pediu para enxugar o catálogo: são excluídos jogos com as 6 dezenas pares, as 6 ímpares, 3 ou mais dezenas consecutivas, ou mais de 3 dezenas em qualquer faixa de dezena (01–10, 11–20, 21–30, 31–40, 41–50 ou 51–60). O núcleo ([`streamlit/nucleo.py`](streamlit/nucleo.py)) mantém o conjunto completo (`gerar_lotes`) e forma o **catálogo de venda** (`criar_catalogo` → `Catalogo`): os jogos aprovados, na ordem do conjunto completo, agrupados de 5 em 5, com numeração própria. Com as âncoras do cliente são 3.085.625 jogos excluídos, 34.915.975 aprovados e **6.983.195 lotes**. As contagens por motivo podem se sobrepor. O catálogo guarda só 1 bit por jogo (~5 MB) e leva cerca de 20 s para ser montado.

- O app (tela de lotes, arquivos CSV/ZIP, conferidor e simulador) usa o catálogo. O painel **Jogos excluídos do catálogo** mostra os totais por regra.
- Como os jogos excluídos saem, as dezenas deixam de aparecer exatamente o mesmo número de vezes (diferença inferior a 2,2% entre a dezena mais e a menos frequente).
- O catálogo demo do site é formado por esse catálogo (`tools/gerar_lotes_demo.py`).
- Isso não aumenta a chance de ganhar. Versão das regras em `REGRAS_VERSAO`.

### Catálogo filtrado experimental

[`streamlit/catalogo_filtrado.py`](streamlit/catalogo_filtrado.py) permite testar, isoladamente, a reorganização de jogos em lotes de cinco após excluir jogos com cinco ou mais dezenas da mesma paridade, quatro ou mais consecutivas ou progressão aritmética. `criar_catalogo(ancoras, semente)` percorre o catálogo original e constrói um índice em memória; `gerar_lotes` usa índices de lotes experimentais começando em zero. Se houver jogos aprovados sobrando, a criação falha explicitamente.

No app Streamlit, abra **Catálogo filtrado experimental**, cole os 30 pares no formato `N1: 07, 12; N2: 11, 27; ...` e clique em **Gerar catálogo experimental**. A construção percorre todos os jogos e pode levar alguns minutos e consumir bastante memória; o índice fica apenas na sessão. Os lotes usam um segredo fictício e uma numeração separada. Alterar o texto descarta o catálogo da sessão; também é possível liberá-lo pelo botão.

Esta área não altera as âncoras padrão nem está conectada ao site ou às vendas. O filtro não garante equilíbrio igual entre dezenas nem aumenta a chance de uma combinação. Antes de usá-lo em produção, é necessário versionar e preservar a configuração, criar armazenamento e alocação segura e validar desempenho e regras de negócio.

### Leads no Trello

O formulário da landing envia para `/api/leads` ([`functions/api/leads.js`](functions/api/leads.js)). Configure como secrets da Cloudflare Pages (ou em `.dev.vars` localmente, a partir de [`.dev.vars.example`](.dev.vars.example)):

- `TRELLO_KEY`, `TRELLO_TOKEN`, `TRELLO_LIST_ID` (obrigatórios) e `ALLOWED_ORIGIN` (opcional).
- Para aceitar ambos os domínios do site, configure `ALLOWED_ORIGIN` como `https://senamatch.pages.dev,https://senamatch.com.br` (origens exatas separadas por vírgula). Publique primeiro o código que aceita a lista, atualize a variável e refaça o deploy. Sem `ALLOWED_ORIGIN`, a checagem de origem fica desativada.
- `WHATSAPP_NUMERO` (DDD + número, só dígitos): usado por `/go/whatsapp` ([`functions/go/whatsapp.js`](functions/go/whatsapp.js)) para os botões de WhatsApp, sem expor o número no repositório.
- Nunca coloque chave ou token no HTML nem no repositório.
- Publicação: Cloudflare Pages com diretório de saída `site` (ver [`wrangler.toml`](wrangler.toml)).

Passo a passo completo: [`docs/CHECKLIST_DESENVOLVIMENTO.md`](docs/CHECKLIST_DESENVOLVIMENTO.md). Regras de negócio: [`docs/REGRAS_DE_NEGOCIO.md`](docs/REGRAS_DE_NEGOCIO.md).

### Teste local de confirmação

Execute `npm run test:confirmacao-demo` na raiz do projeto. O teste simula cadastro, confirmação, expiração, reenvio e entrega de cinco jogos do catálogo fictício, tudo em memória. Não envia e-mail, não acessa o Trello nem altera o site. O link `example.invalid` não é acessível pelo navegador. Isso é apenas uma simulação automatizada, não uma implementação de confirmação ou de acesso seguro para produção.
