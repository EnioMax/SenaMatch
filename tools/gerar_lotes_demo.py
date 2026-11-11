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
    # Catálogo de venda: lotes de 5 formados só com jogos aprovados (n.REGRAS_VERSAO); leva ~20 s
    catalogo = n.criar_catalogo(ancoras, semente)
    # Números de lote espalhados por todo o catálogo, com sorteio reproduzível
    numeros = sorted(random.Random(2026).sample(range(1, catalogo.total_lotes + 1), QUANTIDADE))
    _, jogos = catalogo.gerar_lotes(np.array(numeros) - 1)

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
        "totalLotes": catalogo.total_lotes,
        "lotes": lotes,
    }
    SAIDA.write_text(
        "// Arquivo gerado por tools/gerar_lotes_demo.py. Não edite à mão.\n"
        "window.SENAMATCH_DEMO = " + json.dumps(dados, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    print(f"{len(lotes)} lotes de {n.JOGOS_POR_LOTE} jogos gravados em {SAIDA.relative_to(RAIZ)}")
    print(f"Catálogo: {catalogo.total_lotes:,} lotes ({catalogo.total_excluidos:,} jogos excluídos)")


if __name__ == "__main__":
    main()
