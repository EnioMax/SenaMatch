import numpy as np
import pytest

import catalogo_filtrado as c
import nucleo as n


def test_interpretar_ancoras():
    texto = "; ".join(f"N{i + 1}: {2 * i + 1:02d}, {2 * i + 2:02d}" for i in range(30))
    ancoras_teste = [[2 * i + 1, 2 * i + 2] for i in range(30)]
    assert c.interpretar_ancoras(texto) == ancoras_teste
    assert c.interpretar_ancoras(texto.replace("; ", "\n")) == ancoras_teste
    for invalido in ("", texto.replace("N2:", "N3:"), texto.replace("N2: 03, 04", "N2: 01, 04")):
        with pytest.raises(ValueError):
            c.interpretar_ancoras(invalido)


def test_filtros_e_limites():
    jogos = np.array([
        [1, 2, 4, 9, 15, 20],  # três pares
        [2, 4, 6, 8, 10, 11],  # cinco pares
        [1, 3, 5, 7, 9, 10],  # cinco ímpares
        [1, 2, 3, 4, 12, 19],  # quatro consecutivos
        [1, 4, 7, 10, 13, 16],  # progressão
        [1, 2, 3, 8, 12, 15],  # três consecutivos são permitidos
    ])
    assert c.jogos_aprovados(jogos).tolist() == [True, False, False, False, False, True]
    assert c.jogos_aprovados(jogos[:, ::-1]).tolist() == [True, False, False, False, False, True]


@pytest.mark.parametrize("jogo", [
    [[1, 2, 3, 4, 5]], [[1, 2, 3, 4, 5, 61]], [[1, 2, 3, 4, 5, 5]],
    [[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]], [[65537, 2, 3, 4, 5, 6]],
])
def test_jogo_invalido(jogo):
    with pytest.raises(ValueError):
        c.jogos_aprovados(np.array(jogo))


def test_indice_reorganiza_sem_repetir_e_independe_do_tamanho():
    anc = n.ancoras_para_array(n.PADRAO_ANCORAS)
    semente = n.criar_semente("segredo-ficticio", "teste", n.PADRAO_ANCORAS)
    total = 100
    indice = c._criar_indice(anc, semente, total, 13)
    assert np.array_equal(indice, c._criar_indice(anc, semente, total, 31))
    _, originais = n.gerar_lotes(anc, semente, np.arange(total))
    esperados = np.flatnonzero(c.jogos_aprovados(originais).ravel())
    assert np.array_equal(indice, esperados)
    # O catálogo experimental exige lotes completos; aqui limitamos a amostra para testar o acesso.
    indice = indice[: len(indice) // 5 * 5]
    catalogo = c.CatalogoExperimental(anc, semente, indice)
    numeros = np.array([0, catalogo.total_lotes - 1, 1, 0])
    lotes = catalogo.gerar_lotes(numeros)
    assert lotes.shape == (4, 5, 6)
    assert np.array_equal(lotes, originais.reshape(-1, 6)[indice.reshape(-1, 5)[numeros]])
    assert c.jogos_aprovados(lotes).all()
    assert len(np.unique(indice)) == len(indice)
    with pytest.raises(ValueError):
        catalogo.gerar_lotes(np.array([-1]))
    with pytest.raises(ValueError):
        catalogo.gerar_lotes(np.array([catalogo.total_lotes]))
    with pytest.raises(ValueError):
        catalogo.gerar_lotes(np.array([1.5]))


def test_criacao_valida_ancoras_e_sobras(monkeypatch):
    with pytest.raises(ValueError):
        c.criar_catalogo([[1, 2]], 1)
    with pytest.raises(ValueError):
        c.criar_catalogo(n.PADRAO_ANCORAS, 1, 0)
    monkeypatch.setattr(c, "_criar_indice", lambda *args: np.arange(6, dtype=np.uint32))
    with pytest.raises(ValueError, match="1 jogos aprovados"):
        c.criar_catalogo(n.PADRAO_ANCORAS, 1)
