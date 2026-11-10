// Simulação isolada: não é uma implementação de autenticação ou entrega em produção.
import assert from 'node:assert/strict';
import { randomBytes } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';
import { chaveEmail, validarLead } from '../functions/api/leads.js';

const fonte = readFileSync(new URL('../site/data/lotes_demo.js', import.meta.url), 'utf8');
const conteudo = fonte.match(/^window\.SENAMATCH_DEMO = (.+);$/m);
if (!conteudo) throw new Error('Catálogo de demonstração inválido');
const loteDemo = JSON.parse(conteudo[1]).lotes[0];
const leadDemo = {
  nome: 'Pessoa Exemplo',
  email: 'teste@example.invalid',
  whatsapp: '11912345678',
  maior18: true,
  consentimento: true,
};

function criarSimulacao() {
  let agora = 0;
  const leads = new Map();
  const mensagens = [];
  const tokens = new Map();
  const sessoes = new Map();
  const chave = () => randomBytes(32).toString('hex');
  const emailDe = (lead) => chaveEmail(lead.email);

  function enviarConfirmacao(lead) {
    const token = chave();
    tokens.set(token, { email: emailDe(lead), expira: agora + 15 * 60_000, usado: false });
    mensagens.push({
      destinatario: lead.email,
      link: `https://senamatch.example.invalid/confirmar?token=${token}`,
    });
  }

  return {
    mensagens,
    avancarTempo(ms) { agora += ms; },
    cadastrar(dados) {
      const { lead, erro } = validarLead(dados);
      if (erro) throw new Error(`Cadastro inválido: ${erro}`);
      const email = emailDe(lead);
      const existente = [...leads.values()].find((item) =>
        emailDe(item.lead) === email || item.lead.whatsapp === lead.whatsapp);
      if (existente) return;
      leads.set(email, { lead, confirmado: false, lote: null });
      enviarConfirmacao(lead);
    },
    reenviar(email) {
      const registro = leads.get(chaveEmail(email));
      if (!registro || registro.confirmado) return;
      for (const token of tokens.values()) {
        if (token.email === chaveEmail(email)) token.usado = true;
      }
      enviarConfirmacao(registro.lead);
    },
    confirmar(link) {
      const token = tokens.get(new URL(link).searchParams.get('token'));
      if (!token || token.usado || agora >= token.expira) return null;
      token.usado = true;
      const registro = leads.get(token.email);
      registro.confirmado = true;
      registro.lote ??= structuredClone(loteDemo);
      const sessao = chave();
      sessoes.set(sessao, token.email);
      return sessao;
    },
    verLote(sessao) {
      const registro = leads.get(sessoes.get(sessao));
      return registro?.confirmado ? structuredClone(registro.lote) : null;
    },
  };
}

describe('Simulação local de confirmação e lote fictício', () => {
  it('só entrega cinco jogos após confirmação; link é de uso único', () => {
    const sim = criarSimulacao();
    sim.cadastrar(leadDemo);
    assert.equal(sim.mensagens.length, 1);
    assert.equal(sim.mensagens[0].destinatario, leadDemo.email);
    assert.equal(sim.verLote('sem-sessao'), null);
    const sessao = sim.confirmar(sim.mensagens[0].link);
    assert.ok(sessao);
    const lote = sim.verLote(sessao);
    assert.equal(lote.jogos.length, 5);
    assert.ok(lote.jogos.every((jogo) => jogo.length === 6 && new Set(jogo).size === 6));
    assert.deepEqual(lote, loteDemo);
    assert.equal(sim.confirmar(sim.mensagens[0].link), null);
  });

  it('recusa link vencido e permite confirmar após reenvio', () => {
    const sim = criarSimulacao();
    sim.cadastrar(leadDemo);
    const linkAntigo = sim.mensagens[0].link;
    sim.avancarTempo(15 * 60_000);
    assert.equal(sim.confirmar(linkAntigo), null);
    sim.reenviar(leadDemo.email);
    assert.equal(sim.mensagens.length, 2);
    const sessao = sim.confirmar(sim.mensagens[1].link);
    assert.deepEqual(sim.verLote(sessao), loteDemo);
    assert.equal(sim.confirmar(linkAntigo), null);
  });

  it('não cria outro cadastro com o mesmo e-mail ou WhatsApp', () => {
    const sim = criarSimulacao();
    sim.cadastrar(leadDemo);
    sim.cadastrar({ ...leadDemo, email: 'TESTE@example.invalid', whatsapp: '21988887777' });
    sim.cadastrar({ ...leadDemo, email: 'outro@example.invalid' });
    assert.equal(sim.mensagens.length, 1);
  });

  it('invalida o link anterior quando um novo é solicitado', () => {
    const sim = criarSimulacao();
    sim.cadastrar(leadDemo);
    sim.reenviar(leadDemo.email);
    assert.equal(sim.confirmar(sim.mensagens[0].link), null);
    assert.ok(sim.confirmar(sim.mensagens[1].link));
  });

  it('rejeita dados inválidos antes de criar a mensagem simulada', () => {
    const sim = criarSimulacao();
    assert.throws(() => sim.cadastrar({ ...leadDemo, consentimento: false }), /Cadastro inválido/);
    assert.equal(sim.mensagens.length, 0);
  });
});
