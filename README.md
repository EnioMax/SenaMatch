# SenaMatch

O repositório tem duas partes: o programa que gera os jogos e o site que vende os lotes.

| Pasta | O que é | Tecnologia | Como rodar |
|---|---|---|---|
| [`streamlit/`](streamlit) | **Programa**: gerador e conferidor de jogos (núcleo de cálculo, integração com a Caixa, interface) | Python, NumPy, Streamlit | `cd streamlit && SENAMATCH_SECRET=... streamlit run app.py` |
| [`site/`](site) | **Site**: landing de captação, área do cliente e painel do gestor (protótipo) | HTML, JS, Tailwind (CDN) | `npx wrangler pages dev` (com a função de leads) ou `python3 -m http.server -d site` (só páginas) |
| [`functions/`](functions) | **Função de leads** (`POST /api/leads`): grava o lead como cartão no Trello | Cloudflare Pages Functions | `npm test` |
| [`tools/`](tools) | Gerador dos lotes de demonstração do site | Python (usa `streamlit/nucleo.py`) | `streamlit/.venv/bin/python tools/gerar_lotes_demo.py` |
| [`docs/`](docs) | Regras de negócio e checklist de desenvolvimento | Markdown | |

## Programa (`streamlit/`)

- Variáveis de ambiente: `SENAMATCH_SECRET` (obrigatória; também aceita `st.secrets`) e `SENAMATCH_DEV=1` (só desenvolvimento, usa um segredo fictício).
- Testes: `cd streamlit && python3 test_nucleo.py` (ou `pytest`).
- O CI em `.github/workflows/ci.yml` cobre apenas esta parte.

## Site (`site/`)

- O lote é de **5 jogos**, como no programa (7.600.320 lotes). A área do cliente e o painel leem [`site/data/lotes_demo.js`](site/data/lotes_demo.js), gerado pelo núcleo com um **segredo fictício**: são jogos de demonstração, não os da venda. Regere com `tools/gerar_lotes_demo.py`.
- O painel do gestor guarda dados no `localStorage` do navegador, sem autenticação: não use com dados reais.
- Concursos e resultados da área do cliente e do painel são fictícios.

### Leads no Trello

O formulário da landing envia para `/api/leads` ([`functions/api/leads.js`](functions/api/leads.js)). Configure como secrets da Cloudflare Pages (ou em `.dev.vars` localmente, a partir de [`.dev.vars.example`](.dev.vars.example)):

- `TRELLO_KEY`, `TRELLO_TOKEN`, `TRELLO_LIST_ID` (obrigatórios) e `ALLOWED_ORIGIN` (opcional).
- Nunca coloque chave ou token no HTML nem no repositório.
- Publicação: Cloudflare Pages com diretório de saída `site` (ver [`wrangler.toml`](wrangler.toml)).

Passo a passo completo: [`docs/CHECKLIST_DESENVOLVIMENTO.md`](docs/CHECKLIST_DESENVOLVIMENTO.md). Regras de negócio: [`docs/REGRAS_DE_NEGOCIO.md`](docs/REGRAS_DE_NEGOCIO.md).
