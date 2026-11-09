# SenaMatch — Checklist de desenvolvimento do site

Legenda: `[x]` feito · `[ ]` a fazer · **(cliente)** depende de decisão ou aprovação do cliente · **(você)** ação sua, por exigir conta ou credencial.

## Fase 0 — Base e regras (feito)

- [x] Regras de negócio, preços sugeridos e jornada ([REGRAS_DE_NEGOCIO.md](./REGRAS_DE_NEGOCIO.md))
- [x] Landing page de captação ([site/index.html](../site/index.html)): hero, último sorteio, como funciona, pacotes, FAQ, formulário, aviso de jogo responsável
- [x] Lote padronizado em **5 jogos** em todo o site (landing, área do cliente e painel), como no programa
- [x] Jogos de demonstração gerados pelo núcleo real (`nucleo.py`), por [tools/gerar_lotes_demo.py](../tools/gerar_lotes_demo.py), com segredo fictício
- [x] Função de captura de leads para o Trello ([functions/api/leads.js](../functions/api/leads.js)) com 10 testes (`npm test`)
- [x] Área do cliente e painel testados no navegador, sem erros de JavaScript

## Fase 1 — Colocar o protótipo no ar para o cliente testar

1. [ ] **(você)** Trello: criar um quadro (ex.: "SenaMatch Leads") e uma lista (ex.: "Novos leads").
2. [ ] **(você)** Gerar a **API Key** e o **Token** em <https://trello.com/power-ups/admin>. O token precisa de acesso de leitura e escrita ao quadro. Não cole a chave nem o token no chat nem no código.
3. [ ] **(você)** Descobrir o **ID da lista**: abra `https://trello.com/b/<id-do-quadro>.json`, ou adicione `.json` ao fim do endereço do quadro, e procure o `id` da lista.
4. [ ] **(você)** Publicar na Cloudflare Pages: conectar o repositório `EnioMax/SenaMatch`, branch `separar-site`, **diretório de saída `site`**, sem comando de build.
5. [ ] **(você)** Em *Settings → Variables and Secrets* do projeto, criar os secrets `TRELLO_KEY`, `TRELLO_TOKEN`, `TRELLO_LIST_ID` e, depois que o endereço final existir, `ALLOWED_ORIGIN` (ex.: `https://senamatch.pages.dev`).
6. [ ] Fazer um envio real pelo formulário e conferir se o cartão aparece na lista do Trello.
7. [ ] Repetir o mesmo e-mail e confirmar que **não** cria um segundo cartão.
8. [ ] Abrir o site no celular (iPhone e Android) e conferir formulário, botão fixo e leitura.
9. [ ] Enviar o link ao cliente com um roteiro de teste (ver "Roteiro de aprovação" abaixo).
10. [ ] **(cliente)** Aprovar ou listar alterações (textos, preços, identidade visual).

## Fase 2 — Ajustes antes de abrir ao público

- [ ] Aplicar as alterações pedidas pelo cliente
- [ ] **(cliente)** Confirmar os preços e os pacotes (Avulso, Trio, Turbo)
- [ ] Trocar o Tailwind por CDN por um arquivo CSS compilado (velocidade e segurança)
- [ ] Criar as páginas de **Política de Privacidade**, **Termos de uso** e **Reembolso** (com revisão jurídica)
- [ ] Definir **domínio** próprio, razão social e CNPJ para o rodapé
- [ ] Rate limit para `/api/leads` na Cloudflare (WAF), contra envios em massa
- [ ] Confirmação do e-mail (link enviado ao lead) antes de liberar o lote cortesia: hoje basta usar e-mail e WhatsApp novos para pedir outro
- [ ] Trello lista até ~1.000 cartões por consulta: ao passar disso, mover os leads para um banco de dados
- [ ] Instalar a análise de funil (visita → lead → compra) com consentimento de cookies, se aplicável
- [ ] Imagem de compartilhamento (Open Graph), favicon e `robots.txt`/`sitemap.xml`
- [ ] Revisar acessibilidade (contraste, foco, leitor de tela) e desempenho (Lighthouse ≥ 90)
- [ ] Proteger o painel administrativo: hoje não tem login e guarda dados no navegador. **Não publicar com dados reais antes disso** (ou tirar o link do ar)
- [x] Página do lote (`/meu-lote`) com resultados oficiais da Caixa, simulador (do lote e livre) e ofertas
- [ ] Substituir os dados fictícios de concurso do painel administrativo pela API da Caixa
- [ ] **(você)** Criar o secret `WHATSAPP_NUMERO` na Cloudflare (DDD + número, só dígitos) e refazer o deploy
- [ ] **(você)** Registrar o domínio e criar conta no serviço de e-mail (Resend ou Brevo)
- [ ] Confirmação por e-mail: token por lead (KV), e-mail de boas-vindas e liberação do lote em `/meu-lote?t=...`

## Fase 3 — Venda de verdade (backend)

- [ ] **(cliente)** Escolher o gateway de pagamento (Mercado Pago, Asaas ou Stripe) e abrir a conta
- [ ] Definir o **código global único** e as âncoras de venda, e guardar o `SENAMATCH_SECRET` em gerenciador de segredos (nunca no repositório)
- [ ] Backend FastAPI reaproveitando `nucleo.py`: alocação aleatória e atômica de lotes, sem repetir (`UNIQUE(numero_lote)`)
- [ ] Banco de dados: clientes, pedidos, lotes vendidos e jogos apostados (modelo na seção 5 das regras)
- [ ] Checkout Pix e cartão, com webhook assinado e idempotente
- [ ] Acesso por link mágico por e-mail (sem senha)
- [ ] Migrar `meu-lote.html` para ler os lotes do cliente logado, no lugar do catálogo de demonstração
- [ ] Entrega automática por e-mail e WhatsApp (API oficial)
- [ ] Lote cortesia: alocar o lote ao lead e enviar (hoje o lead só vira cartão no Trello)

## Fase 4 — Retenção e operação

- [ ] Job pós-sorteio: buscar resultado na Caixa, conferir todos os lotes, avisar quem teve quadra, quina ou sena
- [ ] Painel administrativo real, com login, estoque, vendas e leads
- [ ] Assinatura por concurso (**cliente** decide)
- [ ] Campanha da **Mega da Virada**
- [ ] Teste A/B de preço (Avulso e Trio)
- [ ] Mover leads do Trello para um CRM ou banco quando o volume crescer

## Roteiro de aprovação (para o cliente)

1. Abrir a página inicial no celular e no computador: o texto e a oferta estão claros?
2. Enviar o formulário com seus próprios dados: chegou a confirmação?
3. Abrir a página do lote (`/meu-lote`): os 5 jogos do lote estão corretos? Copiar um jogo, marcar "Já apostei" e tentar a conferência.
4. Abrir o painel (`/admin.html`): o estoque, os clientes e a central de sorteios fazem sentido?
5. Os preços, os pacotes e o aviso de jogo responsável estão aprovados?
6. Anotar o que mudar: textos, cores, ordem das seções, imagens.

> Os jogos, os concursos e os resultados da área do cliente e do painel são **de demonstração**. Os lotes reais só existem depois da Fase 3.
