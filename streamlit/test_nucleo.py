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
    assert n.JOGOS_POR_LOTE == 5
    assert n.TOTAL_LOTES == 7_600_320
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
    # Cabeçalho: Lote;Jogo;D1;D2;D3;D4;D5;D6
    assert linhas[0].strip() == n.CABECALHO_CSV.strip()
    assert len(linhas) == 1 + (fim - ini) * 5
    campos = linhas[1].split(";")
    # Lote (7 chars), Jogo (1 char), 6 dezenas = 8 campos
    assert campos[0] == f"{ini + 1:07d}" and campos[1] == "1" and len(campos) == 8
    _, lote_ini = n.gerar_lotes(ANC, SEMENTE, np.array([ini]))
    for k in range(5):
        assert [int(c) for c in linhas[1 + k].split(";")[2:]] == list(lote_ini[0, k])
        assert linhas[1 + k].split(";")[:2] == [f"{ini + 1:07d}", str(k + 1)]
    assert linhas[-1].split(";")[0] == f"{fim:07d}" and linhas[-1].split(";")[1] == "5"
    linhas1 = n.gerar_csv(n.PADRAO_ANCORAS, SEMENTE, 1).decode().splitlines()
    assert len(linhas1) == 1 + 960_000


def test_lotes_de_5_jogos():
    assert (n.TOTAL_GRUPOS, n.LOTES_POR_GRUPO, n.PASSO_DE_HERANCA) == (118_755, 64, 23_751)
    # Exemplos da regra: lote L = G*64 + m; jogo k do grupo (G + k*23751), bloco 5*G' + (m+k)%5, posição m
    for lote, esperado in {
        0: [(0, 0), (118_756, 0), (237_512, 0), (356_268, 0), (475_024, 0)],
        1: [(1, 1), (118_757, 1), (237_513, 1), (356_269, 1), (475_020, 1)],
        64: [(5, 0), (118_761, 0), (237_517, 0), (356_273, 0), (475_029, 0)],
    }.items():
        pos, j = n.origem_dos_jogos(np.array([lote]), np.arange(5))
        assert list(zip(pos[0].tolist(), j[0].tolist())) == esperado
    # O jogo 1 fica no próprio grupo; os outros vêm de grupos diferentes
    todos = np.arange(0, n.TOTAL_LOTES, 13)
    pos, _ = n.origem_dos_jogos(todos, np.arange(5))
    assert (pos[:, 0] // 5 == todos // 64).all()
    assert all(len(set((pos[i] // 5).tolist())) == 5 for i in range(0, len(todos), 500))
    for lote in (0, 1, 5000, 593_774, 7_600_319):
        pos, j = n.origem_dos_jogos(np.array([lote]), np.arange(5))
        assert ((pos >= 0) & (pos < n.TOTAL_BLOCOS) & (j >= 0) & (j < 64)).all()
        volta, k = n.lote_do_jogo(pos, j)
        assert (volta == lote).all() and (k[0] == np.arange(5)).all()
    # Bijeção: cada (bloco, jogo) do conjunto é o jogo de exatamente um (lote, k)
    vistos = np.zeros(n.TOTAL_JOGOS, dtype=np.uint8)
    for ini in range(0, n.TOTAL_LOTES, 400_000):
        pos, j = n.origem_dos_jogos(np.arange(ini, min(ini + 400_000, n.TOTAL_LOTES)), np.arange(5))
        np.add.at(vistos, (pos * 64 + j).ravel(), 1)
    assert vistos.min() == 1 and vistos.max() == 1
    # A inversa devolve o (lote, k) original
    lotes_amostra = np.arange(0, n.TOTAL_LOTES, 997)
    pos, j = n.origem_dos_jogos(lotes_amostra, np.arange(5))
    volta, k = n.lote_do_jogo(pos, j)
    assert (volta == lotes_amostra[:, None]).all() and (k == np.arange(5)).all()
    lotes = np.array([0, 1, 5000, 593_774, 7_600_319])
    colunas, jogos = n.gerar_lotes(ANC, SEMENTE, lotes)
    assert jogos.shape == (5, 5, 6) and colunas.shape == (5, 5, 6)
    for i, lote in enumerate(lotes):
        assert len({tuple(j) for j in jogos[i]}) == 5
        assert (np.diff(jogos[i].astype(int), axis=1) > 0).all()  # dezenas em ordem crescente
        for k in range(5):
            p, j = n.origem_dos_jogos(np.array([lote]), np.array([k]))
            esperado = sorted(n.gerar_blocos(ANC, SEMENTE, p[0])[1][0, j[0, 0]])
            assert list(jogos[i, k]) == esperado
        for jogo, cols in zip(jogos[i], colunas[i]):
            assert all(int(d) in ANC[c] for d, c in zip(jogo, cols))
    # A ordem dos 64 jogos de cada bloco é uma permutação (cada padrão aparece uma vez)
    ordem = n._ordem_dos_jogos(SEMENTE, np.arange(0, n.TOTAL_BLOCOS, 7))
    assert (np.sort(ordem, axis=1) == np.arange(64)).all()
    # Cada dezena aparece o mesmo número de vezes no conjunto redistribuído
    contagem = np.zeros(61, dtype=np.int64)
    for ini in range(0, n.TOTAL_LOTES, 400_000):
        _, js = n.gerar_lotes(ANC, SEMENTE, np.arange(ini, min(ini + 400_000, n.TOTAL_LOTES)))
        contagem += np.bincount(js.ravel(), minlength=61)
    assert set(contagem[1:]) == {n.JOGOS_POR_DEZENA}


def test_csv_dezenas_crescentes():
    pares = list(range(60, 0, -1))
    ancoras = [pares[i : i + 2] for i in range(0, 60, 2)]
    semente = n.criar_semente("s", "7", ancoras)
    linhas = n.gerar_csv(ancoras, semente, 40).decode().splitlines()[1:2000]
    for linha in linhas:
        dz = [int(c) for c in linha.split(";")[2:]]
        assert dz == sorted(dz) and len(set(dz)) == 6


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


def test_ancoras_padrao_personalizadas():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        caminho = Path(d) / "ancoras_padrao.json"
        assert n.carregar_ancoras_padrao(caminho) == n.PADRAO_ANCORAS  # sem arquivo: 01..60
        nova = [[2 * i + 2, 2 * i + 1] for i in range(30)][::-1]
        n.salvar_ancoras_padrao(nova, caminho)
        assert n.carregar_ancoras_padrao(caminho) == nova
        # não salva âncoras inválidas e preserva o padrão salvo
        for invalida in ([[1, 1]] + nova[1:], nova[:29], [[None, 2]] + nova[1:], [[0, 61]] + nova[1:]):
            try:
                n.salvar_ancoras_padrao(invalida, caminho)
                assert False, "deveria falhar"
            except ValueError:
                pass
        assert n.carregar_ancoras_padrao(caminho) == nova
        # arquivo corrompido ou inválido volta ao 01..60
        caminho.write_text("{ruim", encoding="utf-8")
        assert n.carregar_ancoras_padrao(caminho) == n.PADRAO_ANCORAS
        caminho.write_text("[[1,1]]", encoding="utf-8")
        assert n.carregar_ancoras_padrao(caminho) == n.PADRAO_ANCORAS
        n.salvar_ancoras_padrao(nova, caminho)
        n.remover_ancoras_padrao(caminho)
        n.remover_ancoras_padrao(caminho)  # idempotente
        assert n.carregar_ancoras_padrao(caminho) == n.PADRAO_ANCORAS


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
        assert rapido == {k: completo[k] for k in ("contagem", "melhor", "cobertura")}, sorteio


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
            assert n.resumir_sorteio(ancoras, sorteio) == {k: r[k] for k in ("contagem", "melhor", "cobertura")}
            cont, melhor = forca_bruta(ancoras, semente, sorteio)
            assert r["contagem"] == cont, (sorteio, r["contagem"], cont)
            assert r["melhor"] == melhor, (sorteio, r["melhor"], melhor)
            assert len(r["acertos"]) == sum(cont.values())
            assert (np.diff(r["acertos"]) <= 0).all()
            if len(r["acertos"]):
                d, b, j = r["dezenas"][0], r["blocos"][0], r["jogos"][0]
                assert 1 <= j <= 5
                _, jogos = n.gerar_lotes(anc, semente, np.array([b - 1]))
                assert list(jogos[0, j - 1]) == list(d)
                assert len(set(map(int, d)) & set(sorteio)) == r["acertos"][0]


def test_interpretar_lotes():
    lotes, erros = n.interpretar_lotes("25, 100-102 1.000 101-103")
    assert erros == [] and lotes.tolist() == [24, 99, 100, 101, 102, 999]  # 0-based, ordenados, sem repetição
    assert n.interpretar_lotes("  ") == (None, [])
    for ruim in ("abc", "10-5", "0", f"{n.TOTAL_LOTES + 1}", f"1-{n.MAX_LOTES_SELECIONADOS + 1}"):
        lotes, erros = n.interpretar_lotes(ruim)
        assert lotes is None and len(erros) == 1, ruim
    assert len(n.interpretar_lotes(f"1-{n.MAX_LOTES_SELECIONADOS}")[0]) == n.MAX_LOTES_SELECIONADOS


def test_conferir_lotes_igual_ao_conjunto_inteiro():
    sorteios = [(4, 12, 23, 43, 45, 60), (1, 2, 3, 4, 5, 6)]
    completos = [n.conferir_sorteio(n.PADRAO_ANCORAS, SEMENTE, s) for s in sorteios]
    # todos os lotes premiados de um sorteio, mais alguns avulsos: o recorte tem de ser idêntico ao do conjunto inteiro
    escolhidos = np.unique(np.concatenate([completos[0]["blocos"] - 1, np.array([0, 1, 5000, n.TOTAL_LOTES - 1])]))
    recorte = n.conferir_lotes(n.PADRAO_ANCORAS, SEMENTE, escolhidos, sorteios)
    for s, completo, r in zip(sorteios, completos, recorte):
        esperado = n.filtrar_premiados(completo, lotes=escolhidos)
        assert r["jogos_conferidos"] == len(escolhidos) * n.JOGOS_POR_LOTE
        assert r["contagem"] == {m: int((esperado["acertos"] == m).sum()) for m in (4, 5, 6)}, s
        for chave in ("blocos", "jogos", "dezenas", "acertos"):
            assert np.array_equal(r[chave], esperado[chave]), (s, chave)
    # lotes sem premiados
    r = n.conferir_lotes(n.PADRAO_ANCORAS, SEMENTE, np.array([0]), [(1, 2, 3, 4, 5, 6)])[0]
    assert len(r["acertos"]) == 0 and r["contagem"] == {4: 0, 5: 0, 6: 0} and r["melhor"] <= 3


def test_filtros_e_ranking():
    r = {
        "acertos": np.array([6, 5, 5, 4, 4]),
        "blocos": np.array([10, 10, 20, 10, 30]),
        "jogos": np.array([1, 3, 3, 2, 5]),
        "dezenas": np.arange(30).reshape(5, 6),
    }
    f = n.filtrar_premiados(r, faixas=(5, 6), lotes=np.array([9]), jogos=(3,))
    assert f["acertos"].tolist() == [5] and f["blocos"].tolist() == [10] and f["jogos"].tolist() == [3]
    assert len(n.filtrar_premiados(r, faixas=())["acertos"]) == 0
    assert len(n.filtrar_premiados(r)["acertos"]) == 5  # sem filtros: tudo
    assert n.filtrar_premiados(r, jogos=(3, 5))["blocos"].tolist() == [10, 20, 30]
    rk = n.ranking_por_lote(r)
    assert rk["lote"].tolist() == [10, 20, 30]
    assert rk["sena"].tolist() == [1, 0, 0] and rk["quina"].tolist() == [1, 1, 0] and rk["quadra"].tolist() == [1, 0, 1]
    assert rk["melhor"].tolist() == [6, 5, 4]
    assert len(n.ranking_por_lote(n.filtrar_premiados(r, faixas=()))["lote"]) == 0


def test_rotulos_e_nomes():
    sorteios = [("Concurso 1", (1, 2, 3, 4, 5, 6)), ("Concurso 1", (7, 8, 9, 10, 11, 12)), ("Concurso 1", (1, 2, 3, 4, 5, 7))]
    unicos, repetidos = n.rotulos_unicos(sorteios)
    assert [r for r, _ in unicos] == ["Concurso 1", "Concurso 1 (2)", "Concurso 1 (3)"]
    assert [d for _, d in unicos] == [d for _, d in sorteios] and repetidos == ["Concurso 1"]
    assert n.rotulos_unicos([("A", (1, 2, 3, 4, 5, 6))])[1] == []
    assert n.nome_de_arquivo("Concurso 2800 (23/10/2026)") == "Concurso_2800_23_10_2026"
    assert n.nome_de_arquivo("///") == "sorteio"


def test_retorno():
    r = n.calcular_retorno({6: 1, 5: 2, 4: 10}, {6: 1000.0, 5: 100.0, 4: 10.0}, 20, 6.0)
    assert r["premio"] == 1000 + 200 + 100 and r["investido"] == 120 and r["saldo"] == 1180
    assert abs(r["roi"] - 1180 / 120 * 100) < 1e-9
    assert n.calcular_retorno({6: 0, 5: 0, 4: 0}, {}, 0, 6.0)["roi"] is None


def test_caixa_normalizar():
    import caixa

    ok = {
        "numero": 2800,
        "dataApuracao": "23/10/2026",
        "listaDezenas": ["60", "04", "12", "23", "43", "45"],
        "listaRateioPremio": [
            {"faixa": 1, "valorPremio": 0.0},
            {"faixa": 2, "valorPremio": 50000.5},
            {"faixa": 3, "valorPremio": 900.0},
            {"faixa": 4, "valorPremio": 5.0},
            {"faixa": 3, "valorPremio": float("nan")},
        ],
    }
    c = caixa.normalizar(ok)
    assert c["numero"] == 2800 and c["dezenas"] == (4, 12, 23, 43, 45, 60) and c["data"] == "23/10/2026"
    assert c["premios"] == {6: 0.0, 5: 50000.5, 4: 900.0}
    for ruim in (None, [], {}, {**ok, "listaDezenas": ["1", "1", "2", "3", "4", "5"]}, {**ok, "listaDezenas": ["1", "2"]},
                 {**ok, "listaDezenas": ["0", "2", "3", "4", "5", "6"]}, {**ok, "numero": 0}, {**ok, "numero": "x"}):
        assert caixa.normalizar(ruim) is None, ruim
    assert caixa.normalizar({**ok, "listaRateioPremio": "lixo"})["premios"] == {}


if __name__ == "__main__":
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_"):
            fn()
            print("ok", nome)
