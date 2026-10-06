"""
SenaMatch - núcleo de cálculo (sem Streamlit).

Estrutura:
  - 30 colunas (N1..N30), cada uma com 2 dezenas âncora (as 60 dezenas, todas distintas).
  - Um BLOCO é a escolha de 6 colunas entre as 30: C(30,6) = 593.775 blocos.
  - Cada bloco gera 2^6 = 64 jogos (1 dezena de cada coluna escolhida): 38.001.600 jogos.
  - Cada dezena aparece no mesmo número de jogos (3.800.160): igualdade exata.

O código do apostador e o segredo (HMAC) definem a ORDEM dos blocos e a ordem dos
64 jogos dentro de cada bloco. Mesmo código + mesmas âncoras -> sempre o mesmo lote.
Tudo é calculado sob demanda (por faixa de blocos), sem guardar os 38 milhões de jogos.
"""

import hashlib
import hmac
from functools import lru_cache
from itertools import chain, combinations
from math import ceil, comb

import numpy as np

NUM_COLUNAS = 30
COLUNAS_POR_BLOCO = 6
DEZENAS_POR_COLUNA = 2
JOGOS_POR_BLOCO = DEZENAS_POR_COLUNA**COLUNAS_POR_BLOCO  # 64
TOTAL_BLOCOS = comb(NUM_COLUNAS, COLUNAS_POR_BLOCO)  # 593.775
TOTAL_JOGOS = TOTAL_BLOCOS * JOGOS_POR_BLOCO  # 38.001.600
JOGOS_POR_DEZENA = comb(NUM_COLUNAS - 1, COLUNAS_POR_BLOCO - 1) * JOGOS_POR_BLOCO // DEZENAS_POR_COLUNA
DEZENA_MIN, DEZENA_MAX = 1, 60

# 15.000 blocos = 960.000 jogos por arquivo: cabe no limite de linhas do Excel (1.048.576)
BLOCOS_POR_ARQUIVO = 15_000
TOTAL_ARQUIVOS = ceil(TOTAL_BLOCOS / BLOCOS_POR_ARQUIVO)

PADRAO_ANCORAS = [[2 * i + 1, 2 * i + 2] for i in range(NUM_COLUNAS)]

CABECALHO_CSV = "Bloco;Jogo;Colunas;D1;D2;D3;D4;D5;D6\n"
BYTES_POR_LINHA_CSV = 46

# Jogo k (0..63) escolhe, na coluna j, a dezena de índice = bit j de k
BITS = ((np.arange(JOGOS_POR_BLOCO)[:, None] >> np.arange(COLUNAS_POR_BLOCO - 1, -1, -1)) & 1).astype(np.intp)


# ----------------------------------------------------------------------
# Segredo, semente e validação
# ----------------------------------------------------------------------
def criar_semente(segredo: str, codigo: str, ancoras: list[list[int]]) -> int:
    """Semente determinística: depende do código e das âncoras (a ordem das colunas conta)."""
    texto = "/".join(",".join(f"{d:02d}" for d in sorted(col)) for col in ancoras)
    digest = hmac.new(segredo.encode(), f"{codigo}|{texto}".encode(), hashlib.sha256).digest()
    return int.from_bytes(digest, "big")


def criar_id_lote(semente: int) -> str:
    """Identificador curto do lote, ex.: 'A3F9-12BC'."""
    h = f"{semente:064x}"[:8].upper()
    return f"{h[:4]}-{h[4:]}"


def dezenas_repetidas(ancoras: list[list[int]]) -> list[int]:
    todas = [d for col in ancoras for d in col]
    return sorted({d for d in todas if todas.count(d) > 1})


def validar_ancoras(ancoras: list[list[int | None]]) -> list[str]:
    """Lista de problemas (vazia = âncoras válidas)."""
    erros = []
    todas = [d for col in ancoras for d in col]
    if any(d is None for d in todas):
        erros.append("Há células vazias: preencha as 60 dezenas.")
        return erros
    if any(not DEZENA_MIN <= d <= DEZENA_MAX for d in todas):
        erros.append(f"As dezenas devem estar entre {DEZENA_MIN:02d} e {DEZENA_MAX:02d}.")
        return erros
    rep = dezenas_repetidas(ancoras)
    if rep:
        erros.append(
            "Dezenas repetidas: " + ", ".join(f"{d:02d}" for d in rep)
            + ". As 60 âncoras precisam ser todas diferentes."
        )
    return erros


# ----------------------------------------------------------------------
# Blocos e ordem
# ----------------------------------------------------------------------
@lru_cache(maxsize=1)
def todas_combinacoes() -> np.ndarray:
    """(593775, 6): colunas (0..29) de cada bloco, em ordem lexicográfica."""
    plano = np.fromiter(
        chain.from_iterable(combinations(range(NUM_COLUNAS), COLUNAS_POR_BLOCO)),
        dtype=np.uint8,
        count=TOTAL_BLOCOS * COLUNAS_POR_BLOCO,
    )
    return plano.reshape(TOTAL_BLOCOS, COLUNAS_POR_BLOCO)


@lru_cache(maxsize=2)
def ordem_dos_blocos(semente: int) -> np.ndarray:
    """ordem[p] = índice (na lista lexicográfica) do bloco que ocupa a posição p (0-based)."""
    return np.random.default_rng(semente).permutation(TOTAL_BLOCOS).astype(np.int32)


@lru_cache(maxsize=2)
def posicao_dos_blocos(semente: int) -> np.ndarray:
    """Inversa de ordem_dos_blocos: posição de cada bloco."""
    ordem = ordem_dos_blocos(semente)
    inv = np.empty_like(ordem)
    inv[ordem] = np.arange(TOTAL_BLOCOS, dtype=np.int32)
    return inv


def _mistura(x: np.ndarray) -> np.ndarray:
    """splitmix64 vetorizado: embaralhamento reproduzível e de acesso aleatório."""
    x = x + np.uint64(0x9E3779B97F4A7C15)
    x = (x ^ (x >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
    x = (x ^ (x >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
    return x ^ (x >> np.uint64(31))


def _ordem_dos_jogos(semente: int, posicoes: np.ndarray) -> np.ndarray:
    """(n, 64): permutação dos 64 jogos de cada bloco, dependente só de (semente, posição)."""
    chave = np.uint64(semente & 0xFFFFFFFFFFFFFFFF)
    base = posicoes.astype(np.uint64)[:, None] * np.uint64(JOGOS_POR_BLOCO) + np.arange(
        JOGOS_POR_BLOCO, dtype=np.uint64
    )
    with np.errstate(over="ignore"):
        return np.argsort(_mistura(base ^ chave), axis=1)


def ancoras_para_array(ancoras: list[list[int]]) -> np.ndarray:
    return np.asarray(ancoras, dtype=np.uint8).reshape(NUM_COLUNAS, DEZENAS_POR_COLUNA)


def gerar_blocos(ancoras: np.ndarray, semente: int, posicoes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Gera os blocos nas posições dadas (0-based).

    Retorna (colunas (n,6), jogos (n,64,6)); as dezenas de cada jogo saem em ordem crescente
    e os 64 jogos de cada bloco já vêm na ordem definida pelo código do apostador.
    """
    posicoes = np.asarray(posicoes, dtype=np.int64)
    colunas = todas_combinacoes()[ordem_dos_blocos(semente)[posicoes]]
    por_coluna = ancoras[colunas]  # (n, 6, 2)
    jogos = por_coluna[:, np.arange(COLUNAS_POR_BLOCO)[None, :], BITS]  # (n, 64, 6)
    jogos = np.take_along_axis(jogos, _ordem_dos_jogos(semente, posicoes)[:, :, None], axis=1)
    jogos.sort(axis=2)
    return colunas, jogos


# ----------------------------------------------------------------------
# Arquivos CSV
# ----------------------------------------------------------------------
def intervalo_do_arquivo(numero: int) -> tuple[int, int]:
    """Posições [ini, fim) dos blocos do arquivo `numero` (1..TOTAL_ARQUIVOS)."""
    ini = (numero - 1) * BLOCOS_POR_ARQUIVO
    return ini, min(ini + BLOCOS_POR_ARQUIVO, TOTAL_BLOCOS)


def _escrever_2(saida: np.ndarray, col: int, valores: np.ndarray) -> None:
    saida[:, col] = 48 + valores // 10
    saida[:, col + 1] = 48 + valores % 10


def gerar_csv(ancoras: list[list[int]], semente: int, numero_arquivo: int) -> bytes:
    """CSV (separador ';', abre direto no Excel) com os blocos do arquivo, linhas de largura fixa."""
    ini, fim = intervalo_do_arquivo(numero_arquivo)
    posicoes = np.arange(ini, fim)
    colunas, jogos = gerar_blocos(ancoras_para_array(ancoras), semente, posicoes)
    n = len(posicoes) * JOGOS_POR_BLOCO

    saida = np.full((n, BYTES_POR_LINHA_CSV), ord(";"), dtype=np.uint8)
    saida[:, -1] = ord("\n")
    bloco = np.repeat(posicoes + 1, JOGOS_POR_BLOCO)
    for k in range(6):
        saida[:, 5 - k] = 48 + (bloco // 10**k) % 10
    _escrever_2(saida, 7, np.tile(np.arange(1, JOGOS_POR_BLOCO + 1), len(posicoes)))
    cols_linha = np.repeat(colunas.astype(np.int64) + 1, JOGOS_POR_BLOCO, axis=0)
    flat = jogos.reshape(n, 6).astype(np.int64)
    for k in range(6):
        _escrever_2(saida, 10 + 3 * k, cols_linha[:, k])
        saida[:, 10 + 3 * k + 2] = ord(" ") if k < 5 else ord(";")
        _escrever_2(saida, 28 + 3 * k, flat[:, k])
    return CABECALHO_CSV.encode() + saida.tobytes()


# ----------------------------------------------------------------------
# Conferência
# ----------------------------------------------------------------------
def interpretar_sorteios(texto: str) -> tuple[list[tuple[str, tuple[int, ...]]], list[str]]:
    """Lê um sorteio por linha (6 dezenas, separadas por espaço, vírgula, '-' ou ';').

    Uma linha pode ter um rótulo antes de ':' (ex.: 'Concurso 2800: 04 11 25 38 47 59').
    Retorna (sorteios válidos como (rótulo, dezenas), lista de erros).
    """
    sorteios: list[tuple[str, tuple[int, ...]]] = []
    erros: list[str] = []
    for n, linha in enumerate(texto.splitlines(), start=1):
        linha = linha.strip()
        if not linha:
            continue
        rotulo, _, resto = linha.rpartition(":")
        rotulo = rotulo.strip() or f"Sorteio {len(sorteios) + len(erros) + 1}"
        partes = resto.replace(",", " ").replace(";", " ").replace("-", " ").split()
        if not all(p.isdigit() for p in partes):
            erros.append(f"Linha {n}: use apenas números separados por espaço, vírgula ou hífen.")
            continue
        dezenas = [int(p) for p in partes]
        if len(dezenas) != 6:
            erros.append(f"Linha {n}: informe 6 dezenas (encontradas {len(dezenas)}).")
        elif len(set(dezenas)) != 6:
            erros.append(f"Linha {n}: há dezenas repetidas.")
        elif not all(DEZENA_MIN <= d <= DEZENA_MAX for d in dezenas):
            erros.append(f"Linha {n}: as dezenas devem estar entre {DEZENA_MIN:02d} e {DEZENA_MAX:02d}.")
        else:
            sorteios.append((rotulo, tuple(sorted(dezenas))))
    return sorteios, erros


def conferir_sorteio(ancoras: list[list[int]], semente: int, sorteio: tuple[int, ...]) -> dict:
    """Confere o sorteio contra os 38 milhões de jogos sem percorrê-los todos.

    Um jogo só tem 4+ acertos se seu bloco tiver 4+ colunas que contenham dezenas sorteadas;
    só esses blocos (alguns milhares) são gerados e conferidos.
    Retorna: contagem por acertos (4, 5, 6), melhor resultado do lote e os jogos premiados
    (bloco, jogo, dezenas, acertos), ordenados por acertos (desc), bloco e jogo.
    """
    anc = ancoras_para_array(ancoras)
    sorteadas = np.zeros(DEZENA_MAX + 1, dtype=bool)
    sorteadas[list(sorteio)] = True

    por_coluna = sorteadas[anc].sum(axis=1)  # (30,): dezenas sorteadas em cada coluna
    ativa = por_coluna > 0
    # Cada coluna conta no máximo 1 acerto por jogo, e todo conjunto de colunas é um bloco.
    melhor = int(ativa.sum())

    candidatos = np.flatnonzero(ativa[todas_combinacoes()].sum(axis=1) >= 4)
    posicoes = np.sort(posicao_dos_blocos(semente)[candidatos]).astype(np.int64)
    _, jogos = gerar_blocos(anc, semente, posicoes)

    acertos = sorteadas[jogos].sum(axis=2)  # (n, 64)
    b, j = np.nonzero(acertos >= 4)
    n_acertos = acertos[b, j].astype(np.int64)
    ordem = np.lexsort((j, posicoes[b], -n_acertos))
    b, j, n_acertos = b[ordem], j[ordem], n_acertos[ordem]

    return {
        "melhor": min(melhor, 6),
        "contagem": {k: int((n_acertos == k).sum()) for k in (4, 5, 6)},
        "blocos": posicoes[b] + 1,
        "jogos": j + 1,
        "dezenas": jogos[b, j],
        "acertos": n_acertos,
    }
