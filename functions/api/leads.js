// Cloudflare Pages Function: POST /api/leads -> cria um cartão no Trello.
// Segredos (Cloudflare > Settings > Variables and Secrets; localmente em .dev.vars):
//   TRELLO_KEY, TRELLO_TOKEN, TRELLO_LIST_ID  (obrigatórios)
//   ALLOWED_ORIGIN                            (opcional, ex.: https://senamatch.pages.dev)

const TRELLO = 'https://api.trello.com/1';
const LIMITE_CORPO = 2000;

const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj), { status, headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' } });

// Remove quebras de linha e limita o tamanho: o texto vai para o Markdown do cartão
const limpar = (s, max) => String(s ?? '').replace(/[\r\n\t]+/g, ' ').trim().slice(0, max);

export function validarLead(corpo) {
  const c = corpo && typeof corpo === 'object' ? corpo : {};
  const nome = limpar(c.nome, 80);
  const email = limpar(c.email, 120).toLowerCase();
  let whatsapp = String(c.whatsapp ?? '').replace(/\D/g, '');
  if (/^55\d{10,11}$/.test(whatsapp)) whatsapp = whatsapp.slice(2);

  if (nome.length < 2) return { erro: 'nome' };
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) return { erro: 'email' };
  if (!/^[1-9]\d9?\d{8}$/.test(whatsapp)) return { erro: 'whatsapp' };
  if (c.maior18 !== true) return { erro: 'maior18' };
  if (c.consentimento !== true) return { erro: 'consentimento' };
  return { lead: { nome, email, whatsapp, origem: limpar(c.origem, 40) || 'landing' } };
}

const descricao = (l, quando) => [
  `**Nome:** ${l.nome}`,
  `**E-mail:** ${l.email}`,
  `**WhatsApp:** ${l.whatsapp}`,
  `**Origem:** ${l.origem}`,
  `**Maior de 18 anos:** sim`,
  `**Consentimento (lote e resultados por e-mail/WhatsApp):** sim, em ${quando}`,
  `**Status:** lote cortesia pendente`,
].join('\n');

// Forma canônica do e-mail para comparar pessoas: ignora "+etiqueta" e, no Gmail, os pontos
export function chaveEmail(email) {
  const [local = '', dominio = ''] = String(email).toLowerCase().split('@');
  const base = local.split('+')[0];
  const gmail = dominio === 'gmail.com' || dominio === 'googlemail.com';
  return (gmail ? base.replace(/\./g, '') : base) + '@' + (gmail ? 'gmail.com' : dominio);
}

const chaveWhatsapp = (digitos) => {
  const d = String(digitos).replace(/\D/g, '');
  return /^55\d{10,11}$/.test(d) ? d.slice(2) : d;
};

// Procura o e-mail ou o WhatsApp do lead nos cartões existentes, sem depender de como o Trello formatou o texto
export function jaCadastrado(cartoes, lead) {
  const email = chaveEmail(lead.email);
  return cartoes.some((c) => {
    const desc = String(c.desc ?? '').toLowerCase();
    const emails = (desc.match(/[^\s<>()[\]*"',;:]+@[^\s<>()[\]*"',;:]+/g) || []).map(chaveEmail);
    if (emails.includes(email)) return true;
    const zap = desc.match(/whatsapp:[*\s]*([+\d\s().-]+)/);
    return Boolean(zap) && chaveWhatsapp(zap[1]) === lead.whatsapp;
  });
}

async function trello(env, caminho, init = {}) {
  const r = await fetch(TRELLO + caminho, {
    ...init,
    headers: {
      Authorization: `OAuth oauth_consumer_key="${env.TRELLO_KEY}", oauth_token="${env.TRELLO_TOKEN}"`,
      Accept: 'application/json',
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
    },
  });
  if (!r.ok) throw new Error('trello ' + r.status);
  return r.json();
}

export async function onRequestPost({ request, env }) {
  if (!env.TRELLO_KEY || !env.TRELLO_TOKEN || !env.TRELLO_LIST_ID) return json({ ok: false, erro: 'configuracao' }, 500);

  const origem = request.headers.get('Origin');
  if (env.ALLOWED_ORIGIN && origem !== env.ALLOWED_ORIGIN) return json({ ok: false, erro: 'origem' }, 403);
  if (!(request.headers.get('Content-Type') || '').includes('application/json')) return json({ ok: false, erro: 'formato' }, 415);

  const texto = await request.text();
  if (texto.length > LIMITE_CORPO) return json({ ok: false, erro: 'tamanho' }, 413);
  let corpo;
  try { corpo = JSON.parse(texto); } catch { return json({ ok: false, erro: 'formato' }, 400); }

  if (corpo && corpo.site) return json({ ok: true });   // campo isca preenchido: finge sucesso para o robô

  const { lead, erro } = validarLead(corpo);
  if (erro) return json({ ok: false, erro }, 400);

  try {
    // Um lote por pessoa: confere o quadro inteiro (todas as listas e cartões arquivados), por e-mail ou WhatsApp
    const { idBoard } = await trello(env, `/lists/${encodeURIComponent(env.TRELLO_LIST_ID)}?fields=idBoard`);
    const existentes = await trello(env, `/boards/${encodeURIComponent(idBoard)}/cards/all?fields=desc`);
    if (jaCadastrado(existentes, lead)) return json({ ok: true });

    await trello(env, '/cards', {
      method: 'POST',
      body: JSON.stringify({
        idList: env.TRELLO_LIST_ID,
        name: `${lead.nome} · lote cortesia`,
        desc: descricao(lead, new Date().toISOString()),
        pos: 'top',
      }),
    });
    return json({ ok: true });
  } catch {
    return json({ ok: false, erro: 'trello' }, 502);
  }
}

export const onRequest = () => json({ ok: false, erro: 'metodo' }, 405);
