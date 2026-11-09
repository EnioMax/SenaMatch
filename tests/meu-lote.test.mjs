import { test } from 'node:test';
import assert from 'node:assert/strict';
import { normalizar, quantidade, obterSorteios } from '../functions/api/sorteios.js';
import { montarLink } from '../functions/go/whatsapp.js';

const bruto = (numero, dezenas = ['22', '25', '29', '37', '46', '54']) => ({
  numero,
  dataApuracao: '08/11/2026',
  listaDezenas: dezenas,
  listaRateioPremio: [
    { faixa: 1, valorPremio: 1000000.5 },
    { faixa: 2, valorPremio: 23220.26 },
    { faixa: 3, valorPremio: 649.17 },
  ],
});

test('normalizar converte dezenas, data e prêmios', () => {
  assert.deepEqual(normalizar(bruto(3083, ['54', '22', '25', '29', '37', '46'])), {
    numero: 3083,
    data: '08/11/2026',
    dezenas: [22, 25, 29, 37, 46, 54],
    premios: { 6: 1000000.5, 5: 23220.26, 4: 649.17 },
  });
});

test('normalizar rejeita resposta inválida', () => {
  assert.equal(normalizar(null), null);
  assert.equal(normalizar(bruto(1, ['1', '2', '3'])), null);
  assert.equal(normalizar(bruto(1, ['1', '2', '3', '4', '5', '61'])), null);
  assert.equal(normalizar({ ...bruto(1), numero: 'x' }), null);
});

test('quantidade limita entre 1 e 20 e usa 10 por padrão', () => {
  assert.equal(quantidade(null), 10);
  assert.equal(quantidade('abc'), 10);
  assert.equal(quantidade('0'), 10);
  assert.equal(quantidade('5'), 5);
  assert.equal(quantidade('999'), 20);
});

test('obterSorteios busca o último e os anteriores em ordem', async () => {
  const urls = [];
  const buscador = async (url) => {
    urls.push(url);
    const n = Number(url.split('/').pop()) || 3083;
    return { ok: true, json: async () => bruto(n) };
  };
  const r = await obterSorteios(3, buscador);
  assert.deepEqual(r.map((s) => s.numero), [3083, 3082, 3081]);
  assert.equal(urls.length, 3);
});

test('obterSorteios falha se a Caixa falhar', async () => {
  await assert.rejects(obterSorteios(2, async () => ({ ok: false, status: 500 })));
});

test('montarLink monta o link do WhatsApp com DDI 55', () => {
  const l = montarLink('79 9 9999-9999', 'trio');
  assert.match(l, /^https:\/\/wa\.me\/5579999999999\?text=/);
  assert.match(decodeURIComponent(l), /Trio/);
  assert.match(montarLink('5579999999999', 'qualquer'), /wa\.me\/5579999999999/);
});

test('montarLink recusa número ausente ou inválido', () => {
  assert.equal(montarLink(undefined, 'trio'), null);
  assert.equal(montarLink('123', 'trio'), null);
});
