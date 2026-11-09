// Cloudflare Pages Function: GET /api/sorteios?n=13 -> últimos N concursos da Mega-Sena (API pública da Caixa).
// GET /api/sorteios?concurso=3000 -> só esse concurso.
// Resposta: { sorteios: [{ numero, data, dezenas: [6], premios: { 4, 5, 6 } }] }, do mais recente ao mais antigo.

const CAIXA = 'https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena';
const MAX = 20;
const CACHE_SEGUNDOS = 600;

const json = (obj, status = 200, cache = 'no-store') =>
  new Response(JSON.stringify(obj), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': cache },
  });

export function normalizar(d) {
  const dezenas = (d?.listaDezenas ?? []).map(Number).sort((a, b) => a - b);
  const numero = Number(d?.numero);
  if (!Number.isInteger(numero) || dezenas.length !== 6 || dezenas.some((n) => !(n >= 1 && n <= 60))) return null;
  const premios = {};
  for (const r of d.listaRateioPremio ?? []) {
    const acertos = { 1: 6, 2: 5, 3: 4 }[r.faixa];
    if (acertos) premios[acertos] = Number(r.valorPremio) || 0;
  }
  return { numero, data: String(d.dataApuracao ?? ''), dezenas, premios };
}

export function quantidade(valor) {
  const n = Number.parseInt(valor ?? '', 10);
  return Number.isInteger(n) && n >= 1 ? Math.min(n, MAX) : 10;
}

async function buscar(concurso, buscador) {
  const r = await buscador(concurso ? `${CAIXA}/${concurso}` : CAIXA, { headers: { Accept: 'application/json' } });
  if (!r.ok) throw new Error(`caixa ${r.status}`);
  return normalizar(await r.json());
}

export async function obterSorteios(n, buscador = fetch) {
  const ultimo = await buscar(null, buscador);
  if (!ultimo) throw new Error('resposta invalida');
  const numeros = Array.from({ length: n - 1 }, (_, i) => ultimo.numero - 1 - i).filter((x) => x >= 1);
  const anteriores = await Promise.all(numeros.map((x) => buscar(x, buscador)));
  const sorteios = [ultimo, ...anteriores];
  if (sorteios.some((s) => !s)) throw new Error('resposta invalida');
  return sorteios;
}

export async function onRequestGet({ request, waitUntil }) {
  const params = new URL(request.url).searchParams;
  const concurso = params.get('concurso');
  if (concurso !== null && !/^\d{1,5}$/.test(concurso)) return json({ erro: 'concurso' }, 400);
  const n = quantidade(params.get('n'));
  const chave = new Request(`https://cache.senamatch.local/sorteios?${concurso ? `c=${concurso}` : `n=${n}`}`);
  const cache = typeof caches !== 'undefined' ? caches.default : null;

  const guardado = cache && (await cache.match(chave));
  if (guardado) return guardado;

  try {
    let sorteios;
    if (concurso) {
      const unico = await buscar(Number(concurso), fetch);
      if (!unico) throw new Error('resposta invalida');
      sorteios = [unico];
    } else {
      sorteios = await obterSorteios(n);
    }
    const resposta = json({ sorteios }, 200, `public, max-age=${CACHE_SEGUNDOS}`);
    if (cache && waitUntil) waitUntil(cache.put(chave, resposta.clone()));
    return resposta;
  } catch {
    return json({ erro: 'indisponivel' }, concurso ? 404 : 502);
  }
}
