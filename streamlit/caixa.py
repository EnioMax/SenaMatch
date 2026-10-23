"""Consulta somente leitura dos resultados da Mega-Sena na API pública da Caixa (sem Streamlit)."""

import json
import math
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen

API = "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena"
TIMEOUT = 10
MAX_BYTES = 1_000_000
MAX_CONCURSOS = 50
FAIXA_PARA_ACERTOS = {1: 6, 2: 5, 3: 4}


def normalizar(dados) -> dict | None:
    """Aceita só dados válidos: concurso inteiro e 6 dezenas distintas entre 1 e 60.

    Retorna {'numero', 'data', 'dezenas' (ordenadas), 'premios': {acertos: valor por ganhador}}.
    """
    if not isinstance(dados, dict):
        return None
    try:
        numero = int(dados["numero"])
        dezenas = sorted(int(d) for d in dados["listaDezenas"])
    except (KeyError, TypeError, ValueError):
        return None
    if numero < 1 or len(dezenas) != 6 or len(set(dezenas)) != 6 or not all(1 <= d <= 60 for d in dezenas):
        return None
    premios: dict[int, float] = {}
    rateio = dados.get("listaRateioPremio")
    for faixa in rateio if isinstance(rateio, list) else []:
        try:
            acertos = FAIXA_PARA_ACERTOS.get(int(faixa["faixa"]))
            valor = float(faixa["valorPremio"])
        except (KeyError, TypeError, ValueError):
            continue
        if acertos and math.isfinite(valor) and valor >= 0:
            premios[acertos] = valor
    data = str(dados.get("dataApuracao") or "")
    return {"numero": numero, "data": data if len(data) == 10 else "", "dezenas": tuple(dezenas), "premios": premios}


def buscar_concurso(numero: int | None = None) -> dict | None:
    """Um concurso (None = o último). Devolve None se a API falhar ou responder algo inesperado."""
    url = API if numero is None else f"{API}/{int(numero)}"
    pedido = Request(url, headers={"User-Agent": "Mozilla/5.0 SenaMatch", "Accept": "application/json"})
    try:
        with urlopen(pedido, timeout=TIMEOUT) as resposta:
            corpo = resposta.read(MAX_BYTES + 1)
        if len(corpo) > MAX_BYTES:
            return None
        return normalizar(json.loads(corpo))
    except (OSError, ValueError):
        return None


def buscar_ultimos(quantidade: int) -> tuple[list[dict], int]:
    """Os `quantidade` concursos mais recentes (do mais novo ao mais antigo) e quantos falharam."""
    quantidade = max(1, min(int(quantidade), MAX_CONCURSOS))
    ultimo = buscar_concurso()
    if ultimo is None:
        return [], quantidade
    numeros = range(ultimo["numero"] - 1, max(ultimo["numero"] - quantidade, 0), -1)
    with ThreadPoolExecutor(max_workers=6) as pool:
        outros = list(pool.map(buscar_concurso, numeros))
    concursos = [ultimo] + [c for c in outros if c]
    return concursos, quantidade - len(concursos)
