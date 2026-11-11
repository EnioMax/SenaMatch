"""Gera site/data/lotes_demo.js: lotes de 5 jogos calculados pelo núcleo do programa (nucleo.py).

É só para demonstração do site estático: usa um segredo FICTÍCIO e as âncoras padrão,
então estes jogos NÃO são os da venda. O segredo de produção nunca deve aparecer neste repositório.

Uso (a partir da raiz do repositório):
    streamlit/.venv/bin/python tools/gerar_lotes_demo.py
"""

import json
import random
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "streamlit"))

import nucleo as n

SEGREDO_DEMO = "senamatch-demo-publico-nao-usar-em-producao"
CODIGO_DEMO = "demo"
QUANTIDADE = 60
SAIDA = RAIZ / "site" / "data" / "lotes_demo.js"


def main() -> None:
    ancoras = [list(c) for c in n.PADRAO_ANCORAS]
    semente = n.criar_semente(SEGREDO_DEMO, CODIGO_DEMO, ancoras)
    matriz = n.ancoras_para_array(ancoras)
    # Números de lote espalhados por todo o universo (1..7.600.320), com sorteio reproduzível,
    # só entre os lotes aprovados pelas regras de venda (n.REGRAS_VERSAO)
    candidatos = random.Random(2026).sample(range(1, n.TOTAL_LOTES + 1), QUANTIDADE * 3)
    aprovados = n.lotes_aprovados(matriz, semente, np.array([x - 1 for x in candidatos]))
    numeros = sorted(x for x, ok in zip(candidatos, aprovados, strict=True) if ok)[:QUANTIDADE]
    assert len(numeros) == QUANTIDADE
    _, jogos = n.gerar_lotes(matriz, semente, [x - 1 for x in numeros])

    lotes = []
    for numero, lote in zip(numeros, jogos.tolist(), strict=True):
        assert len(lote) == n.JOGOS_POR_LOTE
        assert all(len(set(j)) == 6 and j == sorted(j) for j in lote)
        assert len({tuple(j) for j in lote}) == n.JOGOS_POR_LOTE
        assert not n.jogos_excluidos(np.array(lote)).any()
        lotes.append({"numero": numero, "jogos": lote})

    dados = {
        "aviso": "Lotes de demonstração gerados com segredo fictício. Não são os jogos da venda.",
        "jogosPorLote": n.JOGOS_POR_LOTE,
        "totalLotes": n.TOTAL_LOTES,
        "lotes": lotes,
    }
    SAIDA.write_text(
        "// Arquivo gerado por tools/gerar_lotes_demo.py. Não edite à mão.\n"
        "window.SENAMATCH_DEMO = " + json.dumps(dados, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    print(f"{len(lotes)} lotes de {n.JOGOS_POR_LOTE} jogos gravados em {SAIDA.relative_to(RAIZ)}")
    print(f"Universo: {n.TOTAL_LOTES:,} lotes; cada dezena em {n.JOGOS_POR_DEZENA:,} jogos")


if __name__ == "__main__":
    main()
