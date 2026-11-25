// Middleware da Cloudflare Pages: protege o painel administrativo (/admin e /admin.html) com Basic Auth.
// Segredo (Cloudflare > Settings > Variables and Secrets; localmente em .dev.vars): ADMIN_PASSWORD
// Sem o segredo configurado o painel fica bloqueado (falha fechada).

const ROTA_ADMIN = /^\/admin(\.html)?(\/|$)/;

const igual = (a, b) => {
  const ta = new TextEncoder().encode(a);
  const tb = new TextEncoder().encode(b);
  let dif = ta.length ^ tb.length;
  for (let i = 0; i < Math.max(ta.length, tb.length); i++) dif |= (ta[i] ?? 0) ^ (tb[i] ?? 0);
  return dif === 0;
};

export function senhaCorreta(cabecalho, senha) {
  if (!senha) return false;
  const m = /^Basic\s+(.+)$/i.exec(cabecalho ?? '');
  if (!m) return false;
  let decodificado;
  try { decodificado = new TextDecoder().decode(Uint8Array.from(atob(m[1]), (c) => c.charCodeAt(0))); } catch { return false; }
  const i = decodificado.indexOf(':');
  return i >= 0 && igual(decodificado.slice(i + 1), senha);
}

export async function onRequest({ request, env, next }) {
  if (!ROTA_ADMIN.test(new URL(request.url).pathname)) return next();

  if (!env.ADMIN_PASSWORD) {
    return new Response('Painel indisponível: senha não configurada.', { status: 503, headers: { 'Cache-Control': 'no-store' } });
  }
  if (!senhaCorreta(request.headers.get('Authorization'), env.ADMIN_PASSWORD)) {
    return new Response('Acesso restrito.', {
      status: 401,
      headers: { 'WWW-Authenticate': 'Basic realm="SenaMatch admin", charset="UTF-8"', 'Cache-Control': 'no-store' },
    });
  }
  const resposta = await next();
  const protegida = new Response(resposta.body, resposta);
  protegida.headers.set('Cache-Control', 'no-store');
  protegida.headers.set('X-Robots-Tag', 'noindex, nofollow');
  return protegida;
}
