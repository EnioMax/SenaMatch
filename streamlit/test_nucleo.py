"""Verificações do núcleo. Execute: python test_nucleo.py (compatível com pytest)."""

import io
import random

import numpy as np

import nucleo as n

SEMENTE = n.criar_semente("segredo-teste", "593775", n.PADRAO_ANCORAS)
ANC = n.ancoras_para_array(n.PADRAO_ANCORAS)


def test_constantes():
    assert n.TOTAL_BLOCOS == 593_775
    assert n.TOTAL_JOGOS == 38_001_600
    assert n.JOGOS_POR_DEZENA == 3_800_160
    assert n.TOTAL_ARQUIVOS == 40


def test_ordem_e_reprodutibilidade():
    ordem = n.ordem_dos_blocos(SEMENTE)
    assert np.array_equal(np.sort(ordem), np.arange(n.TOTAL_BLOCOS))
    assert np.array_equal(n.posicao_dos_blocos(SEMENTE)[ordem], np.arange(n.TOTAL_BLOCOS))
    outra = n.criar_semente("segredo-teste", "111111", n.PADRAO_ANCORAS)
    assert not np.array_equal(ordem[:50], n.ordem_dos_blocos(outra)[:50])
    p = np.array([0, 7, 593_774])
    assert np.array_equal(n.gerar_blocos(ANC, SEMENTE, p)[1], n.gerar_blocos(ANC, SEMENTE, p)[1])
    # acesso aleatório: gerar sozinho ou dentro de uma faixa dá o mesmo bloco
    faixa = n.gerar_blocos(ANC, SEMENTE, np.arange(0, 20))[1]
    assert np.array_equal(faixa[7], n.gerar_blocos(ANC, SEMENTE, np.array([7]))[1][0])


def test_bloco_valido():
    colunas, jogos = n.gerar_blocos(ANC, SEMENTE, np.array([123]))
    assert jogos.shape == (1, 64, 6)
    assert len({tuple(j) for j in jogos[0]}) == 64
    permitidas = {int(d) for c in colunas[0] for d in ANC[c]}
    for jogo in jogos[0]:
        assert len(set(jogo)) == 6
        assert all(int(d) in ANC[c] for d, c in zip(jogo, colunas[0]))  # Dk vem da coluna k
        assert set(map(int, jogo)) <= permitidas
        assert len({(int(d) - 1) // 2 for d in jogo}) == 6  # nenhum par repetido no jogo


def test_distribuicao_igual_e_sem_repeticao():
    contagem = np.zeros(61, dtype=np.int64)
    ids = set()
    for ini in range(0, n.TOTAL_BLOCOS, 60_000):
        fim = min(ini + 60_000, n.TOTAL_BLOCOS)
        colunas, jogos = n.gerar_blocos(ANC, SEMENTE, np.arange(ini, fim))
        contagem += np.bincount(jogos.ravel(), minlength=61)
        ids.update(map(bytes, colunas))
    assert len(ids) == n.TOTAL_BLOCOS  # nenhum bloco repetido
    assert set(contagem[1:]) == {n.JOGOS_POR_DEZENA}


def test_csv():
    linhas = n.gerar_csv(n.PADRAO_ANCORAS, SEMENTE, 40).decode().splitlines()
    ini, fim = n.intervalo_do_arquivo(40)
    assert linhas[0] == "Bloco;Jogo;Colunas;D1;D2;D3;D4;D5;D6"
    assert len(linhas) == 1 + (fim - ini) * 64
    campos = linhas[1].split(";")
    assert campos[0] == f"{ini + 1:06d}" and campos[1] == "01" and len(campos) == 9
    colunas, jogos = n.gerar_blocos(ANC, SEMENTE, np.array([ini]))
    assert campos[2] == " ".join(f"{c + 1:02d}" for c in colunas[0])
    assert campos[3:] == [f"{d:02d}" for d in jogos[0, 0]]
    assert linhas[-1].split(";")[0] == f"{fim:06d}" and linhas[-1].split(";")[1] == "64"
    linhas1 = n.gerar_csv(n.PADRAO_ANCORAS, SEMENTE, 1).decode().splitlines()
    assert len(linhas1) == 1 + 960_000


def test_zip():
    import zipfile

    assert n.TOTAL_ZIPS == 8
    assert list(n.arquivos_do_zip(1)) == [1, 2, 3, 4, 5]
    assert list(n.arquivos_do_zip(8)) == [36, 37, 38, 39, 40]
    chamadas = []
    dados = n.gerar_zip(n.PADRAO_ANCORAS, SEMENTE, 8, "x", lambda f, t: chamadas.append((f, t)))
    with zipfile.ZipFile(io.BytesIO(dados)) as zf:
        assert zf.namelist() == [f"x_parte{k}de40.csv" for k in range(36, 41)]
        assert zf.read("x_parte40de40.csv") == n.gerar_csv(n.PADRAO_ANCORAS, SEMENTE, 40)
    assert chamadas[-1] == (5, 5)


def test_validacao_e_sorteios():
    assert n.validar_ancoras(n.PADRAO_ANCORAS) == []
    repetida = [list(c) for c in n.PADRAO_ANCORAS]
    repetida[0][0] = 4
    assert "04" in n.validar_ancoras(repetida)[0]
    assert n.validar_ancoras([[None, 1]] + n.PADRAO_ANCORAS[1:])
    ok, erros = n.interpretar_sorteios("Concurso 1: 4-6-9-13-28-48\n1 2 3\n1 1 2 3 4 5\n0 1 2 3 4 5\n7 8 9 10 11 61")
    assert ok == [("Concurso 1", (4, 6, 9, 13, 28, 48))] and len(erros) == 4


def test_resumo_rapido_aleatorio():
    rnd = random.Random(3)
    for _ in range(300):
        sorteio = tuple(sorted(rnd.sample(range(1, 61), 6)))
        rapido = n.resumir_sorteio(n.PADRAO_ANCORAS, sorteio)
        completo = n.conferir_sorteio(n.PADRAO_ANCORAS, SEMENTE, sorteio)
        assert rapido == {"contagem": completo["contagem"], "melhor": completo["melhor"]}, sorteio


def forca_bruta(ancoras, semente, sorteio):
    anc = n.ancoras_para_array(ancoras)
    sorteadas = np.zeros(61, dtype=bool)
    sorteadas[list(sorteio)] = True
    cont = {4: 0, 5: 0, 6: 0}
    melhor = 0
    for ini in range(0, n.TOTAL_BLOCOS, 30_000):
        _, jogos = n.gerar_blocos(anc, semente, np.arange(ini, min(ini + 30_000, n.TOTAL_BLOCOS)))
        ac = sorteadas[jogos].sum(axis=2)
        melhor = max(melhor, int(ac.max()))
        for k in cont:
            cont[k] += int((ac == k).sum())
    return cont, melhor


def test_conferidor_contra_forca_bruta():
    rnd = random.Random(7)
    pares = list(range(1, 61))
    rnd.shuffle(pares)
    ancoras_custom = [pares[i : i + 2] for i in range(0, 60, 2)]
    sorteios = [
        (4, 6, 9, 13, 28, 48),  # do print do cliente
        (1, 2, 3, 4, 5, 6),  # pares inteiros: no máximo 3 colunas
        tuple(sorted(rnd.sample(range(1, 61), 6))),
    ]
    for ancoras in (n.PADRAO_ANCORAS, ancoras_custom):
        semente = n.criar_semente("s", "42", ancoras)
        anc = n.ancoras_para_array(ancoras)
        extras = [tuple(sorted(int(d) for d in anc[list(c)][:, 0])) for c in ([0, 1, 2, 3, 4, 5], [3, 9, 12, 20, 25, 29])]
        for sorteio in sorteios + extras:
            r = n.conferir_sorteio(ancoras, semente, sorteio)
            assert n.resumir_sorteio(ancoras, sorteio) == {"contagem": r["contagem"], "melhor": r["melhor"]}
            cont, melhor = forca_bruta(ancoras, semente, sorteio)
            assert r["contagem"] == cont, (sorteio, r["contagem"], cont)
            assert r["melhor"] == melhor, (sorteio, r["melhor"], melhor)
            assert len(r["acertos"]) == sum(cont.values())
            assert (np.diff(r["acertos"]) <= 0).all()
            if len(r["acertos"]):
                d, b, j = r["dezenas"][0], r["blocos"][0], r["jogos"][0]
                _, jogos = n.gerar_blocos(anc, semente, np.array([b - 1]))
                assert list(jogos[0, j - 1]) == list(d)
                assert len(set(map(int, d)) & set(sorteio)) == r["acertos"][0]


if __name__ == "__main__":
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_"):
            fn()
            print("ok", nome)
