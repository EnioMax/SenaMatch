# SenaMatch — Regras de negócio da venda de lotes

Status: proposta para validação com o cliente. Itens marcados com **(decidir)** dependem dele.

## 1. Produto

- O produto é o **lote**: 5 jogos de 6 dezenas da Mega-Sena, gerados pelo núcleo ([`streamlit/nucleo.py`](../streamlit/nucleo.py)).
- Universo: o programa gera 38.001.600 jogos distintos. Com as âncoras do cliente e as regras v4 (R13), restam 35.851.049 jogos aprovados: **35.851.045** entram em **7.170.209 lotes numerados**, e os 4 últimos ficam sem lote.
- O cliente compra a **lista de jogos e a conferência**. A aposta é feita por ele nas lotéricas ou no app da Caixa. O SenaMatch **não vende aposta, não recebe prêmio e não intermedeia jogo**.
- Todo jogo tem a mesma chance (1 em 50.063.860). O que o produto entrega: exclusividade do lote, organização e conferência automática. As dezenas não aparecem exatamente o mesmo número de vezes após a exclusão. **Nenhum texto do site pode prometer mais chance de ganhar ou ganhos.**

## 2. Regras

| # | Regra |
|---|---|
| R1 | **Código global único.** Toda a venda usa um único código de catálogo e um único conjunto de âncoras, guardados no servidor. Código por cliente permitiria dois clientes receberem os mesmos jogos. |
| R2 | **Exclusividade.** Um lote nunca é vendido duas vezes. Vale `UNIQUE(numero_lote)` no banco. |
| R3 | **Alocação aleatória e atômica.** Ao confirmar o pagamento, o servidor sorteia N números livres do catálogo (R13) (em transação, com retry em conflito de unicidade). Alocar em sequência entregaria lotes vizinhos, e um lote só é "reservado" depois de pago. |
| R4 | **Segredo só no servidor.** `SENAMATCH_SECRET` nunca vai ao navegador. Os jogos de um lote não vendido não são expostos em nenhuma API. Quem tem o segredo reproduz os 38 milhões de jogos: guardar em gerenciador de segredos e nunca trocá-lo depois de vender. |
| R5 | **Entrega automática** após a confirmação do pagamento (webhook): os lotes aparecem em "Meus lotes" e o cliente recebe aviso por e-mail e, com consentimento, por WhatsApp. |
| R6 | **Acesso sem senha.** E-mail e link mágico de uso único (expira em 15 min). Cada cliente só vê os lotes do próprio `cliente_id`. |
| R7 | **Conferência.** Após cada sorteio (Caixa), um job confere todos os lotes vendidos (`conferir_lotes`) e avisa quem teve quadra, quina ou sena. Quem não teve acerto recebe o resumo na área logada, sem push. |
| R8 | **Lote cortesia (captação).** 1 por pessoa: o mesmo e-mail (ignorando "+etiqueta" e pontos no Gmail) **ou** o mesmo WhatsApp não gera outro lote, em qualquer lista do quadro, inclusive cartões arquivados. A resposta ao visitante é a mesma nos dois casos, para não revelar quem já está cadastrado. Quem usa e-mail e telefone novos não é barrado: a verificação do e-mail (link de confirmação) entra na fase 3. É um lote do mesmo universo, marcado `origem=cortesia`, válido para o próximo concurso e conferido após o sorteio. |
| R9 | **Jogo responsável.** Maioridade (18+) declarada no cadastro e na compra. Aviso fixo de "jogo de sorte" na landing, no checkout e nos e-mails. Sem urgência abusiva ou promessa de retorno. |
| R10 | **LGPD.** Consentimento separado para (a) uso do e-mail para o produto e (b) contato por WhatsApp/marketing. Descadastro em 1 clique, exclusão de dados sob pedido, política de privacidade publicada. |
| R11 | **Reembolso (decidir, com revisão jurídica).** Compra online tem direito de arrependimento de 7 dias (CDC, art. 49). Sugestão: reembolso integral se nenhum sorteio tiver sido conferido com o lote. Depois disso, o lote já foi "usado". |
| R12 | **Lote entregue é definitivo.** Mesmo código, âncoras e lote geram sempre os mesmos jogos (determinístico), então reenvio e reemissão são idênticos. |
| R13 | **Exclusão de jogos (regras v4, pedidas pelo cliente).** Os jogos com as 6 dezenas pares, as 6 ímpares, 4 ou mais dezenas consecutivas (ex.: 22-23-24-25) ou mais de 3 dezenas em uma mesma faixa de dezena (01-10, 11-20, 21-30, 31-40, 41-50 ou 51-60) **não entram em nenhum lote**. Os lotes de 5 são formados só com os jogos aprovados, na ordem do conjunto completo (`nucleo.Catalogo`), com numeração própria. Com as âncoras do cliente: 2.150.551 jogos excluídos, 35.851.049 aprovados, 7.170.209 lotes e 4 jogos aprovados sem lote. As contagens por motivo podem se sobrepor. A numeração dos lotes depende das âncoras, do segredo e da versão das regras: registre `REGRAS_VERSAO` em cada venda e nunca altere as regras depois de vender. A v4 não reproduz os lotes da v3. Isso não aumenta a chance de ganhar (1 em 50.063.860) e a comunicação nunca deve prometer isso. |

## 3. Preços sugeridos (hipótese a validar)

Referência: uma aposta simples da Mega-Sena custa R$ 6,00, então 5 jogos custam R$ 30,00 **na Caixa**. O cliente paga isso separadamente. O preço do SenaMatch é pelo serviço, e deve ficar claro na página que **o valor das apostas não está incluso**.

| Pacote | Lotes (jogos) | Preço | Por lote |
|---|---|---|---|
| Cortesia | 1 (5) | R$ 0 | captação de lead |
| Avulso | 1 (5) | R$ 9,90 | R$ 9,90 |
| **Trio** (destaque) | 3 (15) | R$ 24,90 | R$ 8,30 |
| Turbo | 10 (50) | R$ 69,90 | R$ 6,99 |

- Custo marginal ≈ 0 (o cálculo é instantâneo). O custo real são taxas do gateway (Pix ≈ 1%, cartão ≈ 4–5%) e aquisição de tráfego.
- Sazonal: **Mega da Virada** com pacote próprio (decidir se o cliente quer prêmio e data de corte).
- Fase 2 (**decidir**): assinatura mensal por concurso (ex.: 1 lote novo por sorteio) para receita recorrente.
- Validar com teste A/B (preço do Avulso e do Trio) após as primeiras 200 visitas qualificadas.

## 4. Jornada

1. **Visitante** chega na landing, vê o último sorteio e a proposta.
2. **Lead:** pede o lote cortesia (nome, e-mail, WhatsApp, 18+, consentimento). Recebe e-mail com link mágico, e o lote aparece na área do cliente.
3. **Pós-sorteio:** e-mail "seu lote cortesia foi conferido: N acertos" com CTA para o pacote Trio.
4. **Compra:** escolhe o pacote, paga por Pix ou cartão, o webhook confirma, o servidor aloca e entrega.
5. **Uso:** Meus lotes → copiar, baixar CSV, marcar jogos apostados, ver conferência.
6. **Retenção:** aviso a cada sorteio, oferta do próximo concurso.

## 5. Modelo de dados (mínimo)

- `clientes(id, nome, email UNIQUE, whatsapp, maior_18, consent_produto, consent_marketing, criado_em)`
- `pedidos(id, cliente_id, pacote, qtd_lotes, valor, status[pendente|pago|reembolsado], gateway_ref UNIQUE, criado_em)`
- `lotes_vendidos(numero_lote PRIMARY KEY, cliente_id, pedido_id NULL, origem[venda|cortesia], concurso_alvo, criado_em)`
- `apostados(numero_lote, jogo 1..5, marcado_em)`
- `conferencias(concurso, numero_lote, melhor_acerto, jogos_premiados)`
- `links_magicos(token_hash, cliente_id, expira_em, usado_em)`
- Os jogos **não** são guardados: são recalculados com `gerar_lotes(...)` ao exibir.

## 6. API (backend FastAPI reaproveitando `nucleo.py`)

| Método e rota | Função |
|---|---|
| `POST /leads` (hoje `POST /api/leads`, função da Cloudflare) | Valida 18+, consentimento e honeypot, evita duplicar por e-mail e grava o lead como cartão no **Trello** (chave e token só como secrets). A alocação do lote cortesia entra na fase 3. |
| `POST /auth/link` e `GET /auth/verificar` | Link mágico. |
| `GET /meus-lotes` | Lotes e jogos do cliente autenticado. |
| `POST /pedidos` | Cria o pedido e a cobrança (Pix ou cartão). |
| `POST /webhooks/pagamento` | Confirma o pagamento (assinatura verificada, idempotente) e aloca os lotes. |
| `GET /conferencia/{concurso}` | Resultado da conferência dos lotes do cliente. |
| Job pós-sorteio | Busca o resultado na Caixa, confere e notifica. |

Segurança: rate limit em `/leads` e `/auth/*`, CORS restrito ao domínio, tokens de sessão httpOnly, painel administrativo atrás de login real (o atual usa `localStorage`, sem autenticação).

## 7. Landing page (fase 1)

Meta única: **capturar o lead via lote cortesia**. Estrutura: hero com CTA → último sorteio (prova de conferência) → como funciona (3 passos) → o que você recebe → pacotes (em breve, com a lista de espera) → FAQ (inclusive o que o produto não faz) → formulário de lead → jogo responsável e rodapé legal. Implementada em [`site/index.html`](../site/index.html).

Pendências técnicas da landing: configurar os secrets do Trello na Cloudflare (ver [CHECKLIST_DESENVOLVIMENTO.md](./CHECKLIST_DESENVOLVIMENTO.md)), trocar o Tailwind CDN por build, publicar política de privacidade e termos, e instalar a análise de funil (visita → lead → compra). Os dados pessoais ficam no Trello (servidores possivelmente fora do Brasil): isso consta no aviso de privacidade e deve ser revisado juridicamente.

## 8. Fases

1. **Landing e captura** (pronta; leads no Trello assim que os secrets forem configurados).
2. **Backend, link mágico, alocação, checkout Pix e cartão, Meus lotes** reais (a área do cliente já usa lotes de 5 jogos, mas lê um catálogo de demonstração gerado pelo núcleo).
3. **Conferência pós-sorteio, notificações, painel administrativo real, assinatura.**

## 9. Decisões pendentes

Preços finais, gateway (Mercado Pago, Asaas ou Stripe), canal de WhatsApp (API oficial), política de reembolso, assinatura na fase 2, domínio e razão social/CNPJ para o rodapé, e revisão jurídica dos textos (publicidade de jogos e CDC).
