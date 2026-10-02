"""
SenaMatch - Simulador de Lotes (v3)

Regra do lote:
  - As 6 colunas definem as 6 POSIÇÕES do jogo (Coluna 1 = 1ª posição, etc.).
  - Cada coluna tem 2 dezenas âncora que se alternam na sua posição.
  - Como 2^6 = 64, o lote fechado é o produto das colunas: cada jogo escolhe
    1 dezena de cada coluna e nenhum jogo se repete.
  - Cada dezena aparece em exatamente 32 jogos (distribuição igual).
  - Os jogos NÃO seguem ordem crescente: a posição vem da coluna.

O código do apostador e o segredo do servidor definem a ORDEM dos jogos e o
ID do lote (HMAC). Mesmo código + mesmas colunas -> sempre o mesmo lote.

Segredo: defina SENAMATCH_SECRET em st.secrets (Streamlit Cloud) ou como variável de ambiente.
"""

import hashlib
import hmac
import itertools
import os
import random

import pandas as pd
import streamlit as st

# ----------------------------------------------------------------------
# Constantes
# ----------------------------------------------------------------------
NUM_COLUNAS = 6
PARES_POR_COLUNA = 2
TOTAL_JOGOS = PARES_POR_COLUNA ** NUM_COLUNAS  # 2^6 = 64
DEZENA_MIN, DEZENA_MAX = 1, 60

# True  -> a ordem dos 64 jogos é embaralhada de forma fixa por apostador
# False -> ordem sequencial (a Coluna 1 muda mais devagar, a Coluna 6 mais rápido)
EMBARALHAR_ORDEM = True

PADROES = [(21, 24), (1, 2), (3, 4), (5, 6), (7, 8), (9, 10)]

# Uma cor por coluna (tons que funcionam em tema claro e escuro)
CORES = ["#d97706", "#059669", "#2563eb", "#9333ea", "#dc2626", "#db2777"]

ESTILO_BOLA = (
    "display:inline-flex;align-items:center;justify-content:center;"
    "width:34px;height:34px;border-radius:50%;font-weight:600;font-size:14px;"
    "box-sizing:border-box;"
)


# ----------------------------------------------------------------------
# Segredo e semente
# ----------------------------------------------------------------------
def obter_segredo() -> tuple[str, bool]:
    """Retorna (segredo, seguro). 'seguro' é False no modo de desenvolvimento."""
    try:
        return str(st.secrets["SENAMATCH_SECRET"]), True
    except Exception:
        pass
    segredo = os.environ.get("SENAMATCH_SECRET")
    if segredo:
        return segredo, True
    return "segredo-de-desenvolvimento", False


def criar_semente(segredo: str, codigo: str, colunas: list[list[int]]) -> int:
    """Semente determinística: depende do código e das colunas (a ordem das colunas conta)."""
    texto_colunas = "/".join(",".join(f"{d:02d}" for d in sorted(col)) for col in colunas)
    base = f"{codigo}|{texto_colunas}"
    digest = hmac.new(segredo.encode(), base.encode(), hashlib.sha256).digest()
    return int.from_bytes(digest, "big")


def criar_id_lote(semente: int) -> str:
    """Identificador curto do lote, ex.: 'A3F9-12BC'."""
    h = f"{semente:064x}"[:8].upper()
    return f"{h[:4]}-{h[4:]}"


# ----------------------------------------------------------------------
# Regra de negócio
# ----------------------------------------------------------------------
def dezenas_repetidas(colunas: list[list[int]]) -> list[int]:
    """Dezenas que aparecem mais de uma vez entre as 12 âncoras."""
    todas = [d for col in colunas for d in col]
    return sorted({d for d in todas if todas.count(d) > 1})


def gerar_lote(colunas: list[list[int]], rng: random.Random | None) -> list[tuple[int, ...]]:
    """Produto das colunas: 64 jogos únicos, cada um com 1 dezena por coluna/posição."""
    jogos = list(itertools.product(*colunas))
    if rng is not None:
        rng.shuffle(jogos)
    return jogos


def formatar_jogo(numero: int, jogo: tuple[int, ...]) -> str:
    return f"Jogo {numero:02d}: " + " - ".join(f"{d:02d}" for d in jogo)


# ----------------------------------------------------------------------
# Exibição
# ----------------------------------------------------------------------
def estilo_cor(coluna: int, primeira: bool) -> str:
    """1ª dezena da coluna = bolinha cheia; 2ª dezena = bolinha vazada."""
    cor = CORES[coluna]
    if primeira:
        return f"background:{cor};color:#fff;border:2px solid {cor};"
    return f"background:transparent;color:{cor};border:2px solid {cor};"


def html_legenda(colunas: list[list[int]]) -> str:
    itens = "".join(
        f'<span style="margin-right:18px;white-space:nowrap;">'
        f'<b style="color:{CORES[c]};">Coluna {c + 1}</b>: ● {col[0]:02d} &nbsp;○ {col[1]:02d}</span>'
        for c, col in enumerate(colunas)
    )
    return f'<div style="line-height:2;margin-bottom:8px;">{itens}</div>'


def html_lote(lote: list[tuple[int, ...]], colunas: list[list[int]]) -> str:
    linhas = []
    for n, jogo in enumerate(lote, start=1):
        bolas = "".join(
            f'<span style="{ESTILO_BOLA}{estilo_cor(c, d == colunas[c][0])}">{d:02d}</span>'
            for c, d in enumerate(jogo)
        )
        linhas.append(
            '<div style="display:flex;align-items:center;gap:6px;margin:4px 0;">'
            f'<span style="min-width:70px;font-weight:600;">Jogo {n:02d}</span>{bolas}</div>'
        )
    return (
        '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));'
        'column-gap:24px;">' + "".join(linhas) + "</div>"
    )


def mostrar_resultado(res: dict) -> None:
    lote = res["lote"]
    colunas = res["colunas"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Jogos no lote", len(lote))
    c2.metric("ID do lote", res["id"])
    c3.metric("Jogos por dezena", len(lote) // PARES_POR_COLUNA)
    c4.metric("Posições (colunas)", NUM_COLUNAS)

    aba_visual, aba_copiar = st.tabs(["🎨 Visualização", "📋 Copiar lote"])

    with aba_visual:
        st.caption(
            "A posição de cada dezena no jogo é a sua coluna. "
            "Bolinha cheia = 1ª dezena da coluna; bolinha vazada = 2ª dezena."
        )
        st.markdown(html_legenda(colunas), unsafe_allow_html=True)
        st.markdown(html_lote(lote, colunas), unsafe_allow_html=True)

        st.subheader("Distribuição das dezenas no lote")
        linhas = []
        for c, col in enumerate(colunas):
            linhas.append(
                {
                    "Coluna": f"Coluna {c + 1}",
                    "1ª dezena": f"{col[0]:02d}",
                    "Jogos (1ª)": sum(j[c] == col[0] for j in lote),
                    "2ª dezena": f"{col[1]:02d}",
                    "Jogos (2ª)": sum(j[c] == col[1] for j in lote),
                }
            )
        st.table(pd.DataFrame(linhas).set_index("Coluna"))

    with aba_copiar:
        texto = "\n".join(formatar_jogo(n, j) for n, j in enumerate(lote, start=1))
        st.code(texto, language="text")
        st.download_button(
            "⬇️ Baixar TXT",
            data=texto,
            file_name=f"senamatch_{res['codigo']}_{res['id']}.txt",
            mime="text/plain",
            key="btn_download",
        )


# ----------------------------------------------------------------------
# Interface
# ----------------------------------------------------------------------
st.set_page_config(page_title="SenaMatch - Simulador de Lotes", page_icon="🎯", layout="wide")

segredo, segredo_seguro = obter_segredo()

with st.sidebar:
    st.title("Identificação")
    codigo_apostador = st.text_input("Código do Apostador Base", value="593775", key="codigo_apostador")
    if not segredo_seguro:
        st.warning(
            "Modo de desenvolvimento: defina SENAMATCH_SECRET para que os lotes "
            "sejam exclusivos e não reproduzíveis por terceiros."
        )

st.title("🎯 SenaMatch - Simulador de Lotes")
st.write(
    "Gerador exclusivo de 64 jogos baseado em 6 colunas "
    "(com 2 campos de pares cada) para o apostador base."
)

st.subheader("Configuração das Âncoras (6 Colunas / 2 Pares por Coluna)")
st.caption(
    "Cada coluna é uma posição do jogo: as 2 dezenas da Coluna 1 se alternam na 1ª posição "
    "(32 jogos cada), e o mesmo vale para as demais colunas."
)

colunas_cfg: list[list[int]] = []
for i, area in enumerate(st.columns(NUM_COLUNAS)):
    with area:
        st.markdown(f"**Coluna {i + 1}**")
        par: list[int] = []
        for j in range(PARES_POR_COLUNA):
            valor = st.number_input(
                f"Dezena {j + 1}",
                min_value=DEZENA_MIN,
                max_value=DEZENA_MAX,
                value=PADROES[i][j],
                step=1,
                format="%02d",
                key=f"ancora_col{i + 1}_dez{j + 1}",
            )
            par.append(int(valor))
        colunas_cfg.append(par)

repetidas = dezenas_repetidas(colunas_cfg)
if repetidas:
    st.error(
        "Dezenas repetidas: " + ", ".join(f"{d:02d}" for d in repetidas)
        + ". As 12 âncoras precisam ser todas diferentes."
    )

st.divider()

if st.button(
    "🚀 Gerar Lote Exclusivo de 64 Jogos",
    type="primary",
    key="btn_gerar",
    disabled=bool(repetidas),
):
    codigo = codigo_apostador.strip()
    if not codigo:
        st.error("Informe o Código do Apostador Base na barra lateral.")
    else:
        semente = criar_semente(segredo, codigo, colunas_cfg)
        rng = random.Random(semente) if EMBARALHAR_ORDEM else None
        lote = gerar_lote(colunas_cfg, rng)
        # Guarda o resultado para sobreviver a reruns (ex.: clique em Baixar TXT)
        st.session_state["resultado"] = {
            "codigo": codigo,
            "colunas": [list(c) for c in colunas_cfg],
            "lote": lote,
            "id": criar_id_lote(semente),
        }
        st.success(f"✅ Lote de {TOTAL_JOGOS} jogos gerado com sucesso para o apostador {codigo}!")

resultado = st.session_state.get("resultado")
if resultado:
    if resultado["codigo"] != codigo_apostador.strip() or resultado["colunas"] != colunas_cfg:
        st.info("As âncoras ou o código foram alterados. Clique em gerar para criar o novo lote.")
    mostrar_resultado(resultado)