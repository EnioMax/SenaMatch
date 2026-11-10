"""Experimento isolado: reorganiza jogos aprovados, sem alterar o catálogo existente.

O índice é mantido em memória e identifica jogos pela posição no catálogo original.
Não é um mecanismo de venda, armazenamento ou atribuição a clientes.
"""

import re
from dataclasses import dataclass

import numpy as np

import nucleo as n


def interpretar_ancoras(texto: str) -> list[list[int]]:
    """Lê 30 pares N1: 07, 12; ... em ordem, sem salvar a configuração."""
    entradas = [entrada.strip() for entrada in re.split(r"[;\n]+", texto) if entrada.strip()]
    if len(entradas) != n.NUM_COLUNAS:
        raise ValueError("Informe os 30 pares, separados por ponto e vírgula ou em linhas.")
    ancoras = []
    for numero, entrada in enumerate(entradas, 1):
        trecho = re.fullmatch(r"(?:N(\d+)\s*:\s*)?(\d{1,2})\s*[, ]\s*(\d{1,2})", entrada, re.IGNORECASE)
        if not trecho or (trecho[1] and int(trecho[1]) != numero):
            raise ValueError(f"Confira o par N{numero}: use, por exemplo, N{numero}: 07, 12.")
        ancoras.append([int(trecho[2]), int(trecho[3])])
    erros = n.validar_ancoras(ancoras)
    if erros:
        raise ValueError("; ".join(erros))
    return ancoras


def jogos_aprovados(jogos: np.ndarray) -> np.ndarray:
    """Máscara para jogos com 2 a 4 pares, sem 4 consecutivos ou progressão."""
    jogos = np.asarray(jogos)
    if jogos.ndim < 2 or jogos.shape[-1] != 6:
        raise ValueError("Jogos devem ter seis dezenas na última dimensão.")
    if not np.issubdtype(jogos.dtype, np.integer):
        raise ValueError("As dezenas devem ser números inteiros.")
    if np.any((jogos < 1) | (jogos > 60)):
        raise ValueError("Cada jogo deve ter seis dezenas distintas entre 1 e 60.")
    ordenados = np.sort(jogos.astype(np.int16), axis=-1)
    diferencas = np.diff(ordenados, axis=-1)
    if np.any(diferencas == 0):
        raise ValueError("Cada jogo deve ter seis dezenas distintas entre 1 e 60.")
    pares = (ordenados % 2 == 0).sum(axis=-1)
    consecutivos = diferencas == 1
    sequencia = np.zeros(pares.shape, dtype=bool)
    for i in range(3):
        sequencia |= consecutivos[..., i : i + 3].all(axis=-1)
    progressao = (diferencas == diferencas[..., :1]).all(axis=-1)
    return (pares >= 2) & (pares <= 4) & ~sequencia & ~progressao


def _criar_indice(ancoras: np.ndarray, semente: int, total_lotes: int, tamanho: int) -> np.ndarray:
    partes = []
    for inicio in range(0, total_lotes, tamanho):
        fim = min(inicio + tamanho, total_lotes)
        _, jogos = n.gerar_lotes(ancoras, semente, np.arange(inicio, fim))
        aprovados = jogos_aprovados(jogos).reshape(-1)
        posicoes = np.flatnonzero(aprovados).astype(np.uint32)
        partes.append(posicoes + inicio * n.JOGOS_POR_LOTE)
    return np.concatenate(partes) if partes else np.empty(0, dtype=np.uint32)


@dataclass(frozen=True)
class CatalogoExperimental:
    """Catálogo em memória; numeração de lotes é separada da numeração original."""

    ancoras: np.ndarray
    semente: int
    indice: np.ndarray

    @property
    def total_lotes(self) -> int:
        return len(self.indice) // n.JOGOS_POR_LOTE

    def gerar_lotes(self, numeros: np.ndarray) -> np.ndarray:
        """Retorna jogos dos lotes experimentais com índices inteiros 0-based."""
        numeros = np.asarray(numeros)
        if numeros.ndim != 1 or not np.issubdtype(numeros.dtype, np.integer):
            raise ValueError("Informe uma lista de índices inteiros de lotes.")
        if np.any(numeros < 0) or np.any(numeros >= self.total_lotes):
            raise ValueError("Índice de lote fora do catálogo experimental.")
        ids = self.indice.reshape(-1, n.JOGOS_POR_LOTE)[numeros.astype(np.int64)]
        originais = ids // n.JOGOS_POR_LOTE
        posicoes = ids % n.JOGOS_POR_LOTE
        _, jogos = n.gerar_lotes(self.ancoras, self.semente, originais.reshape(-1))
        selecionados = jogos[np.arange(ids.size), posicoes.reshape(-1)]
        return selecionados.reshape(len(numeros), n.JOGOS_POR_LOTE, 6)


def criar_catalogo(ancoras: list[list[int]], semente: int, tamanho: int = 50_000) -> CatalogoExperimental:
    """Filtra o catálogo inteiro; rejeita sobras em vez de descartá-las."""
    if len(ancoras) != n.NUM_COLUNAS or any(len(par) != 2 for par in ancoras):
        raise ValueError("São necessários 30 pares de âncoras.")
    if any(not isinstance(d, int) or isinstance(d, bool) for par in ancoras for d in par):
        raise ValueError("As âncoras devem ser números inteiros.")
    erros = n.validar_ancoras(ancoras)
    if erros:
        raise ValueError("; ".join(erros))
    if not isinstance(tamanho, int) or isinstance(tamanho, bool) or tamanho <= 0:
        raise ValueError("O tamanho da faixa deve ser um inteiro positivo.")
    matriz = n.ancoras_para_array(ancoras).copy()
    indice = _criar_indice(matriz, semente, n.TOTAL_LOTES, tamanho)
    if len(indice) % n.JOGOS_POR_LOTE:
        raise ValueError(f"O catálogo tem {len(indice) % n.JOGOS_POR_LOTE} jogos aprovados sem lote completo.")
    matriz.flags.writeable = False
    indice.flags.writeable = False
    return CatalogoExperimental(matriz, semente, indice)
