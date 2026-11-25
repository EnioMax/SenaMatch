import { test } from 'node:test';
import assert from 'node:assert/strict';
import { onRequest, senhaCorreta } from '../functions/_middleware.js';

const basic = (usuario, senha) => 'Basic ' + Buffer.from(`${usuario}:${senha}`).toString('base64');
const chamar = (caminho, env, auth) =>
  onRequest({
    request: new Request('https://senamatch.pages.dev' + caminho, { headers: auth ? { Authorization: auth } : {} }),
    env,
    next: async () => new Response('conteudo'),
  });

test('senhaCorreta aceita só a senha configurada, com qualquer usuário', () => {
  assert.equal(senhaCorreta(basic('admin', 'segredo'), 'segredo'), true);
  assert.equal(senhaCorreta(basic('x', 'segredo:com:dois-pontos'), 'segredo:com:dois-pontos'), true);
  assert.equal(senhaCorreta(basic('admin', 'errada'), 'segredo'), false);
  assert.equal(senhaCorreta('Basic ???', 'segredo'), false);
  assert.equal(senhaCorreta(null, 'segredo'), false);
  assert.equal(senhaCorreta(basic('admin', ''), ''), false);
});

test('rotas do painel exigem senha e falham fechadas sem ADMIN_PASSWORD', async () => {
  for (const caminho of ['/admin', '/admin.html', '/admin/']) {
    assert.equal((await chamar(caminho, { ADMIN_PASSWORD: 's' })).status, 401);
    assert.equal((await chamar(caminho, {}, basic('a', 's'))).status, 503);
    const ok = await chamar(caminho, { ADMIN_PASSWORD: 's' }, basic('a', 's'));
    assert.equal(ok.status, 200);
    assert.equal(ok.headers.get('X-Robots-Tag'), 'noindex, nofollow');
  }
});

test('as demais rotas passam sem senha', async () => {
  for (const caminho of ['/', '/meu-lote', '/api/leads', '/administrador']) {
    assert.equal((await chamar(caminho, {})).status, 200);
  }
});
