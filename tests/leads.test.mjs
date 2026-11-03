import assert from 'node:assert/strict';
import { afterEach, beforeEach, describe, it } from 'node:test';
import { onRequest, onRequestPost, validarLead } from '../functions/api/leads.js';

const ENV = { TRELLO_KEY: 'k', TRELLO_TOKEN: 't', TRELLO_LIST_ID: 'lista1' };
const LEAD = { nome: 'Maria Silva', email: 'Maria@Exemplo.com', whatsapp: '(11) 91234-5678', maior18: true, consentimento: true, origem: 'landing-cortesia' };

const pedido = (corpo, headers = {}) =>
  new Request('https://site.test/api/leads', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...headers },
    body: typeof corpo === 'string' ? corpo : JSON.stringify(corpo),
  });

describe('validarLead', () => {
  it('normaliza e aceita um lead válido', () => {
    const { lead, erro } = validarLead({ ...LEAD, whatsapp: '+55 (11) 91234-5678' });
    assert.equal(erro, undefined);
    assert.equal(lead.email, 'maria@exemplo.com');
    assert.equal(lead.whatsapp, '11912345678');
  });
  it('recusa campos inválidos e falta de consentimento ou maioridade', () => {
    assert.equal(validarLead({ ...LEAD, nome: ' ' }).erro, 'nome');
    assert.equal(validarLead({ ...LEAD, email: 'x@y' }).erro, 'email');
    assert.equal(validarLead({ ...LEAD, whatsapp: '123' }).erro, 'whatsapp');
    assert.equal(validarLead({ ...LEAD, maior18: false }).erro, 'maior18');
    assert.equal(validarLead({ ...LEAD, consentimento: 'true' }).erro, 'consentimento');
    assert.equal(validarLead(null).erro, 'nome');
  });
  it('tira quebras de linha para não injetar Markdown no cartão', () => {
    assert.equal(validarLead({ ...LEAD, nome: 'Ana\n**Status:** pago' }).lead.nome, 'Ana **Status:** pago');
  });
});

describe('POST /api/leads', () => {
  const original = globalThis.fetch;
  let chamadas;
  let cartoes;
  beforeEach(() => {
    chamadas = [];
    cartoes = [];
    globalThis.fetch = async (url, init = {}) => {
      chamadas.push({ url: String(url), init });
      const corpo = String(url).includes('/lists/') ? cartoes : { id: 'novo' };
      return new Response(JSON.stringify(corpo), { status: 200 });
    };
  });
  afterEach(() => { globalThis.fetch = original; });

  it('cria o cartão no Trello com autenticação por cabeçalho, sem segredo na URL', async () => {
    const r = await onRequestPost({ request: pedido(LEAD), env: ENV });
    assert.equal(r.status, 200);
    assert.deepEqual(await r.json(), { ok: true });
    const criar = chamadas.find((c) => c.init.method === 'POST');
    const dados = JSON.parse(criar.init.body);
    assert.equal(dados.idList, 'lista1');
    assert.match(dados.desc, /\*\*E-mail:\*\* maria@exemplo\.com\n/);
    assert.match(criar.init.headers.Authorization, /oauth_consumer_key="k", oauth_token="t"/);
    assert.ok(chamadas.every((c) => !c.url.includes('token=') && !c.url.includes('key=')));
  });
  it('não duplica o lead do mesmo e-mail', async () => {
    cartoes = [{ desc: '**Nome:** X\n**E-mail:** maria@exemplo.com\n**WhatsApp:** 1' }];
    const r = await onRequestPost({ request: pedido(LEAD), env: ENV });
    assert.equal(r.status, 200);
    assert.ok(!chamadas.some((c) => c.init.method === 'POST'));
  });
  it('responde 400 para dados inválidos e não chama o Trello', async () => {
    const r = await onRequestPost({ request: pedido({ ...LEAD, consentimento: false }), env: ENV });
    assert.equal(r.status, 400);
    assert.equal(chamadas.length, 0);
  });
  it('ignora robôs que preenchem o campo isca', async () => {
    const r = await onRequestPost({ request: pedido({ ...LEAD, site: 'http://spam' }), env: ENV });
    assert.equal(r.status, 200);
    assert.equal(chamadas.length, 0);
  });
  it('recusa origem diferente, formato errado e corpo grande', async () => {
    const env = { ...ENV, ALLOWED_ORIGIN: 'https://senamatch.pages.dev' };
    assert.equal((await onRequestPost({ request: pedido(LEAD, { Origin: 'https://outro.com' }), env })).status, 403);
    const texto = new Request('https://site.test/api/leads', { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: 'x' });
    assert.equal((await onRequestPost({ request: texto, env: ENV })).status, 415);
    assert.equal((await onRequestPost({ request: pedido('x'.repeat(3000)), env: ENV })).status, 413);
    assert.equal((await onRequestPost({ request: pedido('{quebrado'), env: ENV })).status, 400);
  });
  it('falha com 500 sem configuração e 502 se o Trello recusar', async () => {
    assert.equal((await onRequestPost({ request: pedido(LEAD), env: {} })).status, 500);
    globalThis.fetch = async () => new Response('{}', { status: 401 });
    assert.equal((await onRequestPost({ request: pedido(LEAD), env: ENV })).status, 502);
  });
  it('outros métodos retornam 405', async () => {
    assert.equal(onRequest().status, 405);
  });
});
