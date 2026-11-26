# SenaMatch — Checklist de desenvolvimento do site

Legenda: `[x]` feito · `[ ]` a fazer · **(cliente)** depende de decisão ou aprovação do cliente · **(você)** ação sua, por exigir conta ou credencial.

## Plano de execução (análise de 25/11/2026)

Jornada alvo: anúncio no Instagram → landing (simulador, oferta e formulário) → e-mail/WhatsApp de confirmação → página do lote cortesia (lote, simulador, conferidor, vídeo). Marque cada item ao concluir; as fases abaixo detalham o que já existia.

### Etapa 1 — Corrigir o que está errado e proteger o que está exposto

- [x] Landing: trocar "mais de 7 milhões de lotes" por 4.176.479 (regras v5)
- [x] Landing: remover "diferença inferior a 2,2%" e "dezenas distribuídas de forma equilibrada" (a v5 deixa a dezena mais frequente ~18% acima da menos frequente)
- [x] Trocar o selo "Mais escolhido" (sem vendas que o sustentem) por "Recomendado", na landing e na página do lote
- [x] Landing: o texto de sucesso do formulário não promete e-mail/WhatsApp que ainda não são enviados
- [x] Proteger `/admin` com senha (Basic Auth em `functions/_middleware.js`, falha fechada sem `ADMIN_PASSWORD`) e `noindex`
- [x] **(você)** Criar o secret `ADMIN_PASSWORD` na Cloudflare e refazer o deploy (verificado em 25/11: `/admin` responde 401 pedindo senha em `senamatch.pages.dev` e `senamatch.com.br`)
- [x] Branch de produção da Cloudflare trocada de `separar-site` para `main`; a partir de agora o push no `main` publica o site
- [x] **(você)** Criar o secret `WHATSAPP_NUMERO` (DDD + número, só dígitos) na Cloudflare em **Production** e refazer o deploy (verificado em 26/11: `/go/whatsapp` responde 302 para `wa.me` em `senamatch.pages.dev` e `senamatch.com.br`)
- [x] Tirar o botão "Entrar" do menu (abria o lote de demonstração); o exemplo ficou como link "Ver um lote de exemplo" em Como funciona. A pedido do cliente (26/11), também saíram o botão "Lote grátis" do menu e a etiqueta "Lote cortesia grátis para o próximo concurso" do hero; a chamada para o formulário fica nos botões "Quero meu lote grátis"
- [x] Landing: usar `/api/sorteios` no lugar da API da Caixa direto do navegador

### Etapa 2 — Lead → confirmação → lote cortesia (núcleo do funil)

- [x] Registrar `utm_source`, `utm_medium` e `utm_campaign` no lead (a landing lê da URL no envio; o cartão do Trello ganha a linha **UTM**; `origem` continua `landing-cortesia`)
- [ ] **(você)** Registrar o domínio e criar conta no serviço de e-mail (Resend ou Brevo); criar um KV na Cloudflare para os tokens
- [ ] Gerar token por lead (uso único, com validade) e enviar o e-mail de confirmação
- [ ] `GET /confirmar?t=...`: marcar o lead como confirmado e liberar o lote cortesia
- [ ] Botão "Confirmar no WhatsApp" (`wa.me` com o código) como prova do número, sem API oficial
- [ ] `/meu-lote?t=...` lê o lote do lead no servidor; remover `?lote=N&j=...` e o lote de demonstração das rotas reais
- [ ] Reenvio do link de confirmação e tratamento de link expirado ou já usado
- [ ] Texto do formulário e página de "verifique seu e-mail" alinhados ao fluxo

### Etapa 3 — Métricas

- [ ] Análise de funil: visita → clique no CTA → lead → confirmado → compra, respeitando consentimento
- [ ] Painel simples de conversão por campanha (a partir dos UTMs)

### Etapa 4 — Landing que vende

- [ ] Mini-simulador na landing (6 a 15 dezenas contra o último concurso)
- [ ] Formulário curto ou CTA mais cedo na página (hoje o formulário é quase o último bloco)
- [ ] Vídeo explicativo (45 a 60 s) abaixo do hero: hospedagem, legenda e carregamento sob demanda **(cliente: roteiro)**
- [ ] Imagem de compartilhamento (Open Graph), favicon e `robots.txt`/`sitemap.xml`
- [ ] Testar no navegador interno do Instagram (copiar, links externos, `wa.me`)

### Etapa 5 — Página do lote e conferidor

- [ ] Cartão "Comece aqui" com o vídeo no topo da página do lote
- [ ] Conferidor com dezenas digitadas (hoje só busca concurso por número)
- [ ] Após o sorteio: "seu lote foi conferido: N acertos" com chamada para o Trio
- [ ] Ofertas no fim da página, com o botão de compra coerente com o canal definido

### Etapa 6 — Qualidade e requisitos legais

- [ ] Compilar o Tailwind (tirar o CDN)
- [ ] Páginas de Privacidade, Termos e Reembolso **(cliente: revisão jurídica)**
- [ ] Conferir a política de anúncios da Meta para conteúdo ligado a loterias antes de investir em tráfego
- [ ] Lighthouse ≥ 90 e revisão de acessibilidade

### Etapa 7 — Venda de verdade

Ver a Fase 3 abaixo (gateway, backend, alocação atômica, checkout Pix e cartão).

### Sugestões e backlog

Ideias que melhoram o produto, para decidir e puxar para uma etapa conforme avançamos. Marque `[x]` ao implementar e escreva `descartada` ao lado das recusadas.

- [ ] Compartilhar o resultado ("meu lote teve 1 quadra") como imagem, para gerar indicação orgânica
- [ ] Indique um amigo: ganha outro lote cortesia quando o amigo confirmar (1 por pessoa continua valendo)
- [ ] Lembrete antes do sorteio (e-mail/WhatsApp) para o cliente apostar a tempo
- [ ] Opção de receber os avisos só por e-mail ou só por WhatsApp
- [ ] Página pública de resultado do último concurso, para tráfego de busca (SEO)
- [ ] PWA: instalar o `/meu-lote` na tela inicial do celular

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
5. [ ] **(você)** Em *Settings → Variables and Secrets* do projeto, configurar `TRELLO_KEY`, `TRELLO_TOKEN`, `TRELLO_LIST_ID` e `ALLOWED_ORIGIN` como `https://senamatch.pages.dev,https://senamatch.com.br`. Publique o código que aceita a lista antes de alterar a variável e refaça o deploy depois da alteração.
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
- [x] **(você)** Criar o secret `WHATSAPP_NUMERO` na Cloudflare (DDD + número, só dígitos) e refazer o deploy
- [ ] **(você)** Registrar o domínio e criar conta no serviço de e-mail (Resend ou Brevo)
- [ ] Confirmação por e-mail: token por lead (KV), e-mail de boas-vindas e liberação do lote em `/meu-lote?t=...`

- [x] Regras de exclusão v5 (jogos com 6 pares, 6 ímpares, 4+ consecutivas, mais de 3 dezenas na mesma faixa de dez ou soma fora de 150 a 216): lotes formados só com jogos aprovados (`Catalogo`), no núcleo, no app e no catálogo demo
- [ ] **(cliente)** Confirmar as regras v1 e se quer outros critérios (soma, final das dezenas)

## Fase 3 — Venda de verdade (backend)

- [ ] **(cliente)** Escolher o gateway de pagamento (Mercado Pago, Asaas ou Stripe) e abrir a conta
- [ ] Definir o **código global único** e as âncoras de venda, e guardar o `SENAMATCH_SECRET` em gerenciador de segredos (nunca no repositório)
- [ ] Backend FastAPI reaproveitando `nucleo.py`: alocação aleatória e atômica de lotes do `Catalogo` (numeração própria; só jogos aprovados), sem repetir (`UNIQUE(numero_lote)`), registrando `REGRAS_VERSAO`
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
