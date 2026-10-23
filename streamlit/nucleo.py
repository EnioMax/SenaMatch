"""
SenaMatch - núcleo de cálculo (sem Streamlit).

Estrutura:
  - 30 colunas (N1..N30), cada uma com 2 dezenas âncora (as 60 dezenas, todas distintas).
  - Um BLOCO é a escolha de 6 colunas entre as 30: C(30,6) = 593.775 blocos.
  - Cada bloco gera 2^6 = 64 jogos (1 dezena de cada coluna escolhida): 38.001.600 jogos.
  - Cada dezena aparece no mesmo número de jogos (3.800.160): igualdade exata.
  - Os blocos são agrupados de 5 em 5 (118.755 GRUPOS, 320 jogos cada) e cada grupo forma 64 LOTES
    de 5 jogos: 7.600.320 lotes. O lote L (0-based) é o lote m = L % 64 do grupo G = L // 64.
    Herança: o jogo k (0..4) do lote vem da posição m do bloco 5*G' + (m + k) % 5, com
    G' = (G + k*23.751) mod 118.755. O jogo 1 (k=0) fica no próprio grupo; os outros 4 vêm de
    grupos diferentes, espalhados por toda a lista. Cada jogo aparece uma única vez, sem sorteio.

O código do apostador e o segredo (HMAC) definem a ORDEM dos blocos e a ordem dos
64 jogos dentro de cada bloco. Mesmo código + mesmas âncoras -> sempre o mesmo conjunto.
Tudo é calculado sob demanda (por faixa de lotes), sem guardar os 38 milhões de jogos.
"""

import hashlib
import hmac
import io
import json
import os
import re
import zipfile
from functools import lru_cache
from itertools import chain, combinations
from math import ceil, comb
from pathlib import Path

import numpy as np

NUM_COLUNAS = 30
COLUNAS_POR_BLOCO = 6
DEZENAS_POR_COLUNA = 2
JOGOS_POR_BLOCO = DEZENAS_POR_COLUNA**COLUNAS_POR_BLOCO  # 64
TOTAL_BLOCOS = comb(NUM_COLUNAS, COLUNAS_POR_BLOCO)  # 593.775
TOTAL_JOGOS = TOTAL_BLOCOS * JOGOS_POR_BLOCO  # 38.001.600
JOGOS_POR_LOTE = 5
TOTAL_LOTES = TOTAL_JOGOS // JOGOS_POR_LOTE  # 7.600.320
# 5 blocos (5 x 64 = 320 jogos) formam um grupo de 64 lotes de 5 jogos
TOTAL_GRUPOS = TOTAL_BLOCOS // JOGOS_POR_LOTE  # 118.755
LOTES_POR_GRUPO = JOGOS_POR_BLOCO  # 64
PASSO_DE_HERANCA = TOTAL_GRUPOS // JOGOS_POR_LOTE  # 23.751: espalha os 5 jogos de um lote por toda a lista
JOGOS_POR_DEZENA = comb(NUM_COLUNAS - 1, COLUNAS_POR_BLOCO - 1) * JOGOS_POR_BLOCO // DEZENAS_POR_COLUNA
DEZENA_MIN, DEZENA_MAX = 1, 60

# 192.000 lotes = 960.000 jogos por arquivo: cabe no limite de linhas do Excel (1.048.576)
LOTES_POR_ARQUIVO = 192_000
TOTAL_ARQUIVOS = ceil(TOTAL_LOTES / LOTES_POR_ARQUIVO)

# Pacotes ZIP de 5 arquivos (~26 MB) para baixar tudo em poucos downloads
ARQUIVOS_POR_ZIP = 5
TOTAL_ZIPS = ceil(TOTAL_ARQUIVOS / ARQUIVOS_POR_ZIP)

PADRAO_ANCORAS = [[2 * i + 1, 2 * i + 2] for i in range(NUM_COLUNAS)]
ARQUIVO_ANCORAS_PADRAO = Path(__file__).with_name("ancoras_padrao.json")

CABECALHO_CSV = "Lote;Jogo;" + ";".join(f"D{k}" for k in range(1, COLUNAS_POR_BLOCO + 1)) + "\n"
BYTES_PREFIXO_CSV = 10  # 'LLLLLLL;J;'

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
# Âncoras padrão definidas pelo usuário
# ----------------------------------------------------------------------
def carregar_ancoras_padrao(caminho: Path = ARQUIVO_ANCORAS_PADRAO) -> list[list[int]]:
    """Âncoras padrão: as salvas pelo usuário, se o arquivo existir e for válido; senão 01..60."""
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        ancoras = [[int(d) for d in col] for col in dados]
        formato_ok = len(ancoras) == NUM_COLUNAS and all(len(c) == DEZENAS_POR_COLUNA for c in ancoras)
        if formato_ok and not validar_ancoras(ancoras):
            return ancoras
    except (OSError, ValueError, TypeError):
        pass
    return [list(c) for c in PADRAO_ANCORAS]


def salvar_ancoras_padrao(ancoras: list[list[int]], caminho: Path = ARQUIVO_ANCORAS_PADRAO) -> None:
    """Grava as âncoras como padrão (só se válidas). Escrita atômica: nunca deixa o arquivo pela metade."""
    if len(ancoras) != NUM_COLUNAS or any(len(c) != DEZENAS_POR_COLUNA for c in ancoras):
        raise ValueError("Formato inválido: são necessárias 30 colunas com 2 dezenas.")
    erros = validar_ancoras(ancoras)
    if erros:
        raise ValueError(erros[0])
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps([list(c) for c in ancoras]), encoding="utf-8")
    os.replace(temporario, caminho)


def remover_ancoras_padrao(caminho: Path = ARQUIVO_ANCORAS_PADRAO) -> None:
    """Volta ao padrão original (01..60)."""
    caminho.unlink(missing_ok=True)


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


def _ordem_dos_jogos(semente: int, posicoes: np.ndarray, k: np.ndarray | None = None) -> np.ndarray:
    """Padrão (0..63) que ocupa a posição k de cada bloco: permutação afim (a*k + b) mod 64.

    Com `a` ímpar é uma bijeção, então os 64 jogos do bloco aparecem uma vez cada, e o cálculo é
    O(1) por jogo. (a, b) dependem só de (semente, posição). `k` tem o shape de `posicoes`
    (ou (n, 64) se omitido: ordem completa de cada bloco).
    """
    chave = np.uint64(semente & 0xFFFFFFFFFFFFFFFF)
    with np.errstate(over="ignore"):
        h = _mistura(np.asarray(posicoes).astype(np.uint64) ^ chave)
    a = ((h & np.uint64(63)) | np.uint64(1)).astype(np.int64)
    b = ((h >> np.uint64(6)) & np.uint64(63)).astype(np.int64)
    if k is None:
        a, b, k = a[:, None], b[:, None], np.arange(JOGOS_POR_BLOCO, dtype=np.int64)
    return (a * k + b) % JOGOS_POR_BLOCO


def ancoras_para_array(ancoras: list[list[int]]) -> np.ndarray:
    return np.asarray(ancoras, dtype=np.uint8).reshape(NUM_COLUNAS, DEZENAS_POR_COLUNA)


def gerar_blocos(ancoras: np.ndarray, semente: int, posicoes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Gera os blocos de origem (6 colunas + 64 jogos) nas posições dadas (0-based).

    Retorna (colunas (n,6), jogos (n,64,6)); a dezena Dk de cada jogo pertence à k-ésima coluna
    do bloco (colunas em ordem crescente), preservando a ancoragem. O jogo na posição k do bloco
    é o padrão definido por `_ordem_dos_jogos`.
    """
    posicoes = np.asarray(posicoes, dtype=np.int64)
    colunas = todas_combinacoes()[ordem_dos_blocos(semente)[posicoes]]
    por_coluna = ancoras[colunas]  # (n, 6, 2)
    jogos = por_coluna[:, np.arange(COLUNAS_POR_BLOCO)[None, :], BITS]  # (n, 64, 6)
    jogos = np.take_along_axis(jogos, _ordem_dos_jogos(semente, posicoes)[:, :, None], axis=1)
    return colunas, jogos


def origem_dos_jogos(lotes: np.ndarray, k: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(posição do bloco, posição do jogo no bloco) do jogo k (0..4) do lote (0-based).

    Lote L = G*64 + m. O jogo k vem do grupo G' = (G + k*PASSO) mod grupos, do bloco
    5*G' + (m + k) mod 5, na posição m. O jogo 0 (k=0) fica no próprio grupo.
    """
    lotes = np.asarray(lotes, dtype=np.int64)[..., None]
    k = np.asarray(k, dtype=np.int64)
    grupo, m = lotes // LOTES_POR_GRUPO, lotes % LOTES_POR_GRUPO
    grupo_origem = (grupo + k * PASSO_DE_HERANCA) % TOTAL_GRUPOS
    posicao = JOGOS_POR_LOTE * grupo_origem + (m + k) % JOGOS_POR_LOTE
    return posicao, np.broadcast_to(m, posicao.shape)


def lote_do_jogo(posicao_bloco: np.ndarray, j: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Inversa de origem_dos_jogos: (lote 0-based, k 0..4) do jogo j do bloco na posição dada."""
    posicao_bloco = np.asarray(posicao_bloco, dtype=np.int64)
    m = np.asarray(j, dtype=np.int64)
    k = (posicao_bloco % JOGOS_POR_LOTE - m) % JOGOS_POR_LOTE
    grupo = (posicao_bloco // JOGOS_POR_LOTE - k * PASSO_DE_HERANCA) % TOTAL_GRUPOS
    return grupo * LOTES_POR_GRUPO + m, k


def gerar_lotes(ancoras: np.ndarray, semente: int, lotes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Gera os lotes (0-based) com a distribuição por herança: cada lote tem 5 jogos.

    Cada jogo é o jogo j do bloco na posição p dadas por `origem_dos_jogos`. Como
    (lote, k) <-> (bloco, j) é uma bijeção, cada jogo do conjunto aparece exatamente uma vez.
    Retorna (colunas (n,5,6), jogos (n,5,6)): as colunas de origem de cada jogo e as dezenas,
    com as 6 dezenas de cada jogo em ordem crescente (colunas acompanham as dezenas).
    """
    lotes = np.asarray(lotes, dtype=np.int64)
    pos, j = origem_dos_jogos(lotes, np.arange(JOGOS_POR_LOTE))  # (n, 5)
    colunas = todas_combinacoes()[ordem_dos_blocos(semente)[pos]]  # (n, 5, 6)
    padrao = _ordem_dos_jogos(semente, pos, j)  # (n, 5)
    por_coluna = ancoras[colunas]  # (n, 5, 6, 2)
    escolha = BITS[padrao][..., None]  # (n, 5, 6, 1)
    jogos = np.take_along_axis(por_coluna, escolha, axis=3)[..., 0]
    crescente = np.argsort(jogos, axis=-1)
    return np.take_along_axis(colunas, crescente, axis=-1), np.take_along_axis(jogos, crescente, axis=-1)


# ----------------------------------------------------------------------
# Arquivos CSV
# ----------------------------------------------------------------------
def intervalo_do_arquivo(numero: int) -> tuple[int, int]:
    """Lotes [ini, fim) (0-based) do arquivo `numero` (1..TOTAL_ARQUIVOS)."""
    ini = (numero - 1) * LOTES_POR_ARQUIVO
    return ini, min(ini + LOTES_POR_ARQUIVO, TOTAL_LOTES)


def _escrever_2(saida: np.ndarray, col: int, valores: np.ndarray) -> None:
    saida[:, col] = 48 + valores // 10
    saida[:, col + 1] = 48 + valores % 10


def gerar_csv(ancoras: list[list[int]], semente: int, numero_arquivo: int) -> bytes:
    """CSV (separador ';', abre direto no Excel): Lote;Jogo;D1..D6, linhas de largura fixa."""
    ini, fim = intervalo_do_arquivo(numero_arquivo)
    lotes_arquivo = np.arange(ini, fim)
    _, jogos = gerar_lotes(ancoras_para_array(ancoras), semente, lotes_arquivo)
    total_jogos_arquivo = len(lotes_arquivo) * JOGOS_POR_LOTE

    saida = np.full((total_jogos_arquivo, BYTES_PREFIXO_CSV + 3 * COLUNAS_POR_BLOCO), ord(";"), dtype=np.uint8)

    lotes = np.repeat(lotes_arquivo + 1, JOGOS_POR_LOTE)
    for k in range(7):
        saida[:, 6 - k] = 48 + (lotes // 10**k) % 10
    saida[:, 8] = 48 + np.tile(np.arange(1, JOGOS_POR_LOTE + 1), len(lotes_arquivo))
    dezenas = jogos.reshape(total_jogos_arquivo, COLUNAS_POR_BLOCO).astype(np.int64)
    for k in range(COLUNAS_POR_BLOCO):
        _escrever_2(saida, BYTES_PREFIXO_CSV + 3 * k, dezenas[:, k])
    saida[:, -1] = ord("\n")
    return CABECALHO_CSV.encode() + saida.tobytes()


def arquivos_do_zip(numero_zip: int) -> range:
    """Números dos arquivos CSV que compõem o pacote ZIP `numero_zip` (1..TOTAL_ZIPS)."""
    ini = (numero_zip - 1) * ARQUIVOS_POR_ZIP + 1
    return range(ini, min(ini + ARQUIVOS_POR_ZIP, TOTAL_ARQUIVOS + 1))


def gerar_zip(ancoras: list[list[int]], semente: int, numero_zip: int, prefixo: str, progresso=None) -> bytes:
    """ZIP com os CSVs do pacote. `progresso(feitos, total)` é chamado a cada arquivo."""
    arquivos = arquivos_do_zip(numero_zip)
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, numero in enumerate(arquivos):
            zf.writestr(f"{prefixo}_parte{numero:02d}de{TOTAL_ARQUIVOS}.csv", gerar_csv(ancoras, semente, numero))
            if progresso:
                progresso(i + 1, len(arquivos))
    return saida.getvalue()


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


def resumir_sorteio(ancoras: list[list[int]], sorteio: tuple[int, ...]) -> dict:
    """Contagem de Quadras, Quinas e Senas do lote inteiro por combinatória (instantâneo).

    Em cada coluna, a quantidade de dezenas sorteadas é 0, 1 ou 2. Num bloco com i2 colunas
    de 2, i1 de 1 e i0 de 0: as de 2 acertam em qualquer escolha, as de 1 acertam em
    1 das 2 escolhas e as de 0 nunca acertam.
    """
    anc = ancoras_para_array(ancoras)
    sorteadas = np.zeros(DEZENA_MAX + 1, dtype=bool)
    sorteadas[list(sorteio)] = True
    por_coluna = sorteadas[anc].sum(axis=1)
    a2, a1 = int((por_coluna == 2).sum()), int((por_coluna == 1).sum())
    a0 = NUM_COLUNAS - a1 - a2

    contagem = {4: 0, 5: 0, 6: 0}
    for i2 in range(min(a2, COLUNAS_POR_BLOCO) + 1):
        for i1 in range(min(a1, COLUNAS_POR_BLOCO - i2) + 1):
            i0 = COLUNAS_POR_BLOCO - i2 - i1
            if i0 > a0:
                continue
            blocos = comb(a2, i2) * comb(a1, i1) * comb(a0, i0)
            for j in range(i1 + 1):
                if i2 + j >= 4:
                    contagem[i2 + j] += blocos * comb(i1, j) * 2 ** (i2 + i0)
    return {
        "contagem": contagem,
        "melhor": min(a1 + a2, COLUNAS_POR_BLOCO),
        "cobertura": {"duplos": a2, "simples": a1},
    }


def conferir_sorteio(ancoras: list[list[int]], semente: int, sorteio: tuple[int, ...]) -> dict:
    """Confere o sorteio contra os 38 milhões de jogos sem percorrê-los todos.

    Um jogo só tem 4+ acertos se seu bloco tiver 4+ colunas que contenham dezenas sorteadas;
    só esses blocos (alguns milhares) são gerados e conferidos.
    Retorna: contagem por acertos (4, 5, 6), melhor resultado do lote e os jogos premiados
    (lote, jogo, dezenas, acertos), ordenados por acertos (desc), lote e jogo.
    """
    anc = ancoras_para_array(ancoras)
    sorteadas = np.zeros(DEZENA_MAX + 1, dtype=bool)
    sorteadas[list(sorteio)] = True

    por_coluna = sorteadas[anc].sum(axis=1)  # (30,): dezenas sorteadas em cada coluna
    a2, a1 = int((por_coluna == 2).sum()), int((por_coluna == 1).sum())
    ativa = por_coluna > 0
    # Cada coluna conta no máximo 1 acerto por jogo, e todo conjunto de colunas é um bloco.
    melhor = int(ativa.sum())

    # Cada jogo só tem 4+ acertos se seu bloco tiver 4+ colunas que contenham dezenas sorteadas
    candidatos = np.flatnonzero(ativa[todas_combinacoes()].sum(axis=1) >= 4)
    posicoes_blocos = np.sort(posicao_dos_blocos(semente)[candidatos]).astype(np.int64)
    _, jogos = gerar_blocos(anc, semente, posicoes_blocos)

    acertos = sorteadas[jogos].sum(axis=2)  # (n, 64)
    b, j = np.nonzero(acertos >= 4)
    n_acertos = acertos[b, j].astype(np.int64)
    # O jogo j do bloco na posição p é o jogo k do lote L (ver lote_do_jogo)
    lotes, k = lote_do_jogo(posicoes_blocos[b], j)
    ordem = np.lexsort((k, lotes, -n_acertos))
    b, j, k, n_acertos, lotes = b[ordem], j[ordem], k[ordem], n_acertos[ordem], lotes[ordem]

    return {
        "melhor": min(melhor, 6),
        "contagem": {m: int((n_acertos == m).sum()) for m in (4, 5, 6)},
        "blocos": lotes + 1,
        "jogos": k + 1,
        "dezenas": np.sort(jogos[b, j], axis=-1),
        "acertos": n_acertos,
        "cobertura": {"duplos": a2, "simples": a1},
    }


# ----------------------------------------------------------------------
# Conferência por lotes escolhidos, ranking, filtros e retorno financeiro
# ----------------------------------------------------------------------
MAX_LOTES_SELECIONADOS = 100_000  # 500.000 jogos
FAIXAS_PREMIADAS = (6, 5, 4)


def interpretar_lotes(texto: str, total: int = TOTAL_LOTES) -> tuple[np.ndarray | None, list[str]]:
    """Lê uma seleção de lotes como '25, 100-200, 1.000' (1-based).

    Retorna (lotes 0-based, ordenados e sem repetição; None se o texto estiver vazio), erros).
    Em caso de erro, o primeiro item é None.
    """
    texto = texto.strip()
    if not texto:
        return None, []
    faixas: list[tuple[int, int]] = []
    erros: list[str] = []
    for parte in re.split(r"[,;\s]+", texto):
        if not parte:
            continue
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", parte.replace(".", ""))
        if not m:
            erros.append(f"'{parte}' não é um lote nem uma faixa (use, por exemplo, 25 ou 100-200).")
            continue
        ini, fim = int(m[1]), int(m[2] or m[1])
        if ini > fim:
            erros.append(f"Faixa invertida: {parte}.")
        elif ini < 1 or fim > total:
            erros.append(f"'{parte}' está fora do conjunto: os lotes vão de 1 a {total:,}.".replace(",", "."))
        else:
            faixas.append((ini - 1, fim))
    if erros:
        return None, erros
    faixas.sort()
    unidas: list[list[int]] = []
    for ini, fim in faixas:
        if unidas and ini <= unidas[-1][1]:
            unidas[-1][1] = max(unidas[-1][1], fim)
        else:
            unidas.append([ini, fim])
    quantidade = sum(fim - ini for ini, fim in unidas)
    if quantidade > MAX_LOTES_SELECIONADOS:
        limite = f"{MAX_LOTES_SELECIONADOS:,}".replace(",", ".")
        return None, [f"Selecione no máximo {limite} lotes por vez (você escolheu {quantidade:,}).".replace(",", ".")]
    return np.concatenate([np.arange(ini, fim, dtype=np.int64) for ini, fim in unidas]), []


def conferir_lotes(ancoras: list[list[int]], semente: int, lotes: np.ndarray, sorteios: list[tuple[int, ...]]) -> list[dict]:
    """Confere só os lotes dados (0-based) contra cada sorteio, gerando os jogos uma única vez.

    Cada jogo vira uma máscara de bits (bit d = dezena d); os acertos são o popcount de
    (jogo & sorteio). Devolve, por sorteio, o mesmo formato de `conferir_sorteio` mais
    `jogos_conferidos`; `melhor` é o maior número de acertos entre os lotes escolhidos.
    """
    anc = ancoras_para_array(ancoras)
    lotes = np.asarray(lotes, dtype=np.int64)
    mascaras = [np.uint64(sum(1 << d for d in sorteio)) for sorteio in sorteios]
    partes: list[list[tuple[np.ndarray, ...]]] = [[] for _ in sorteios]
    melhor = [0] * len(sorteios)
    for ini in range(0, len(lotes), 20_000):
        grupo = lotes[ini : ini + 20_000]
        _, jogos = gerar_lotes(anc, semente, grupo)
        bits = np.bitwise_or.reduce(np.left_shift(np.uint64(1), jogos.astype(np.uint64)), axis=-1)  # (n, 5)
        for i, mascara in enumerate(mascaras):
            acertos = np.bitwise_count(bits & mascara).astype(np.int64)
            melhor[i] = max(melhor[i], int(acertos.max()))
            idx, k = np.nonzero(acertos >= 4)
            partes[i].append((grupo[idx], k, acertos[idx, k], jogos[idx, k]))
    resultados = []
    for i in range(len(sorteios)):
        vazio = (np.empty(0, np.int64), np.empty(0, np.int64), np.empty(0, np.int64), np.empty((0, COLUNAS_POR_BLOCO), np.uint8))
        lt, k, ac, dz = (np.concatenate(c) for c in zip(*partes[i])) if partes[i] else vazio
        ordem = np.lexsort((k, lt, -ac))
        lt, k, ac, dz = lt[ordem], k[ordem], ac[ordem], dz[ordem]
        resultados.append(
            {
                "melhor": min(melhor[i], 6),
                "contagem": {m: int((ac == m).sum()) for m in (4, 5, 6)},
                "blocos": lt + 1,
                "jogos": k + 1,
                "dezenas": dz,
                "acertos": ac,
                "jogos_conferidos": len(lotes) * JOGOS_POR_LOTE,
            }
        )
    return resultados


def filtrar_premiados(
    r: dict,
    faixas: tuple[int, ...] | None = None,
    lotes: np.ndarray | None = None,
    jogos: tuple[int, ...] | None = None,
) -> dict:
    """Restringe os jogos premiados às faixas (acertos), aos lotes (0-based) e/ou aos jogos (1 a 5) informados."""
    mascara = np.ones(len(r["acertos"]), dtype=bool)
    if faixas is not None:
        mascara &= np.isin(r["acertos"], faixas)
    if lotes is not None:
        mascara &= np.isin(r["blocos"] - 1, lotes)
    if jogos is not None:
        mascara &= np.isin(r["jogos"], jogos)
    return {chave: r[chave][mascara] for chave in ("blocos", "jogos", "dezenas", "acertos")}


def rotulos_unicos(sorteios: list[tuple[str, tuple[int, ...]]]) -> tuple[list[tuple[str, tuple[int, ...]]], list[str]]:
    """Torna os rótulos únicos ('Concurso 1', 'Concurso 1 (2)', ...) e devolve os rótulos que se repetiam."""
    usados: set[str] = set()
    repetidos: list[str] = []
    resultado = []
    for rotulo, dezenas in sorteios:
        novo, contador = rotulo, 1
        while novo in usados:
            contador += 1
            novo = f"{rotulo} ({contador})"
        if novo != rotulo and rotulo not in repetidos:
            repetidos.append(rotulo)
        usados.add(novo)
        resultado.append((novo, dezenas))
    return resultado, repetidos


def nome_de_arquivo(texto: str) -> str:
    """Troca por '_' tudo que não é letra, número ou hífen, para o rótulo servir de nome de arquivo."""
    return re.sub(r"[^\w-]+", "_", texto).strip("_") or "sorteio"


def ranking_por_lote(r: dict) -> dict:
    """Agrupa os jogos premiados por lote: contagem de Sena, Quina e Quadra e melhor resultado.

    Ordenado por Sena, Quina e Quadra (desc) e depois pelo número do lote.
    """
    lotes, acertos = np.asarray(r["blocos"]), np.asarray(r["acertos"])
    if not len(lotes):
        vazio = np.empty(0, np.int64)
        return {"lote": vazio, "sena": vazio, "quina": vazio, "quadra": vazio, "melhor": vazio}
    unicos, inverso = np.unique(lotes, return_inverse=True)
    contar = lambda m: np.bincount(inverso, weights=(acertos == m), minlength=len(unicos)).astype(np.int64)
    sena, quina, quadra = contar(6), contar(5), contar(4)
    melhor = np.zeros(len(unicos), dtype=np.int64)
    np.maximum.at(melhor, inverso, acertos)
    ordem = np.lexsort((unicos, -quadra, -quina, -sena))
    return {
        "lote": unicos[ordem], "sena": sena[ordem], "quina": quina[ordem], "quadra": quadra[ordem], "melhor": melhor[ordem]
    }


def calcular_retorno(contagem: dict[int, int], premios: dict[int, float], jogos: int, valor_aposta: float) -> dict:
    """Prêmio total, capital investido (jogos x valor da aposta), saldo e retorno percentual (ROI)."""
    premio = sum(contagem.get(f, 0) * premios.get(f, 0.0) for f in FAIXAS_PREMIADAS)
    investido = jogos * valor_aposta
    saldo = premio - investido
    return {"premio": premio, "investido": investido, "saldo": saldo, "roi": saldo / investido * 100 if investido else None}
