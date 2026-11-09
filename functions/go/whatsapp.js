// Cloudflare Pages Function: GET /go/whatsapp?t=trio -> redireciona para o WhatsApp do SenaMatch.
// O número fica só na variável WHATSAPP_NUMERO (DDD + número, ex.: 79999999999), nunca no repositório.

const TEXTOS = {
  duvida: 'Olá! Tenho uma dúvida sobre o SenaMatch.',
  avulso: 'Olá! Quero o lote Avulso do SenaMatch.',
  trio: 'Olá! Quero o pacote Trio do SenaMatch.',
  turbo: 'Olá! Quero o pacote Turbo do SenaMatch.',
};

export function montarLink(numero, topico) {
  const digitos = String(numero ?? '').replace(/\D/g, '');
  const completo = /^55\d{10,11}$/.test(digitos) ? digitos : `55${digitos}`;
  if (!/^55[1-9]\d9?\d{8}$/.test(completo)) return null;
  const texto = TEXTOS[topico] ?? TEXTOS.duvida;
  return `https://wa.me/${completo}?text=${encodeURIComponent(texto)}`;
}

export function onRequestGet({ request, env }) {
  const topico = new URL(request.url).searchParams.get('t');
  const link = montarLink(env.WHATSAPP_NUMERO, topico);
  if (!link) return new Response('WhatsApp indisponível no momento.', { status: 503, headers: { 'Cache-Control': 'no-store' } });
  return new Response(null, { status: 302, headers: { Location: link, 'Cache-Control': 'no-store' } });
}
