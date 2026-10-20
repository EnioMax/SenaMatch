"""
SenaMatch - Simulador de Lotes (v4)

Regra do conjunto:
  - 30 colunas (N1..N30), cada uma com 2 dezenas âncora (as 60 dezenas, todas diferentes).
  - Um LOTE é a escolha de 6 colunas entre as 30: C(30;6) = 593.775 lotes.
  - Cada lote gera 2^6 = 64 jogos (1 dezena de cada coluna escolhida), sem repetição.
  - Total do conjunto: 593.775 x 64 = 38.001.600 jogos; cada dezena aparece no mesmo número de jogos.
  - Posição: a dezena ocupa no jogo a posição da sua coluna dentro do lote (colunas em ordem
    crescente). As dezenas de N1 ficam sempre na 1ª posição, independente do valor.
    Os jogos não seguem ordem crescente.

O código do apostador e o segredo do servidor definem a ORDEM dos lotes e dos jogos
(HMAC). Mesmo código + mesmas âncoras -> sempre o mesmo conjunto.
Os jogos são gerados sob demanda e entregues em arquivos CSV (cabem no Excel).

Segredo: defina SENAMATCH_SECRET em st.secrets (Streamlit Cloud) ou como variável de ambiente.
"""

import os

import numpy as np
import pandas as pd
import streamlit as st

import nucleo as n

FAIXAS = {6: "🏆 Sena", 5: "🥈 Quina", 4: "🥉 Quadra"}
MAX_JOGOS_EXIBIDOS = 200
MAX_SORTEIOS = 1000
MAX_DETALHES = 5  # até aqui mostra os jogos premiados de todos os sorteios

# Uma cor por posição de coluna dentro do lote (tons que funcionam em tema claro e escuro)
CORES = ["#d97706", "#059669", "#2563eb", "#9333ea", "#dc2626", "#db2777"]
COR_ACERTO = "#059669"

ESTILO_BOLA = (
    "display:inline-flex;align-items:center;justify-content:center;"
    "width:34px;height:34px;border-radius:50%;font-weight:600;font-size:14px;"
    "box-sizing:border-box;"
)


# ----------------------------------------------------------------------
# Segredo
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


# ----------------------------------------------------------------------
# Exibição
# ----------------------------------------------------------------------
def html_bloco(colunas: np.ndarray, jogos: np.ndarray) -> str:
    """Os 64 jogos de um lote: só as 6 dezenas de cada jogo, da 1ª à 6ª posição."""
    celula = "padding:2px 4px;text-align:center;"
    bola = (
        "display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;"
        "border-radius:50%;font-weight:600;font-size:14px;color:#fff;box-sizing:border-box;"
    )
    cabecalho = "".join(
        f'<th style="{celula}font-size:11px;line-height:1.3;color:{CORES[k]};">{k + 1}ª<br>N{int(c) + 1}</th>'
        for k, c in enumerate(colunas)
    )
    linhas = []
    for num, jogo in enumerate(jogos, start=1):
        celulas = "".join(
            f'<td style="{celula}"><span style="{bola}background:{CORES[k]};">{int(d):02d}</span></td>'
            for k, d in enumerate(jogo)
        )
        linhas.append(f'<tr><td style="padding:2px 8px 2px 0;font-weight:600;white-space:nowrap;">Jogo {num:02d}</td>{celulas}</tr>')
    return (
        '<div style="overflow-x:auto;"><table style="border-collapse:collapse;">'
        f'<thead><tr><th></th>{cabecalho}</tr></thead><tbody>' + "".join(linhas) + "</tbody></table></div>"
    )


def html_jogo_conferido(bloco: int, jogo: int, dezenas: np.ndarray, sorteio: tuple[int, ...]) -> str:
    """Dezenas acertadas em destaque (cheias, com brilho); as demais apagadas."""
    acertos = sorted(int(d) for d in dezenas if int(d) in sorteio)
    bolas = "".join(
        f'<span style="{ESTILO_BOLA}'
        + (
            f"background:{COR_ACERTO};color:#fff;border:2px solid {COR_ACERTO};box-shadow:0 0 0 3px {COR_ACERTO}55;"
            if int(d) in acertos
            else "border:2px solid #9ca3af55;color:#9ca3af;opacity:.5;font-weight:400;"
        )
        + f'">{int(d):02d}</span>'
        for d in dezenas
    )
    lista = ", ".join(f"{d:02d}" for d in acertos)
    return (
        '<div style="display:flex;align-items:center;gap:8px;margin:6px 0;flex-wrap:wrap;">'
        f'<span style="min-width:150px;font-weight:600;">Lote {bloco:06d} · Jogo {jogo:02d}</span>{bolas}'
        f'<span style="margin-left:6px;"><b>{FAIXAS[len(acertos)]} · {len(acertos)} acertos</b>: {lista}</span></div>'
    )


def milhar(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


def mostrar_resultado(res: dict) -> None:
    ancoras = n.ancoras_para_array(res["ancoras"])

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Lotes no conjunto", milhar(n.TOTAL_BLOCOS), help="Cada lote combina 6 das 30 colunas.")
    c2.metric("Jogos por lote", n.JOGOS_POR_BLOCO, help="Uma dezena de cada coluna do lote: 2⁶ = 64 jogos.")
    c3.metric("Jogos no conjunto", milhar(n.TOTAL_JOGOS), help="Todos os lotes juntos.")
    c4.metric("Jogos por dezena", milhar(n.JOGOS_POR_DEZENA), help="Quantos jogos do conjunto contêm cada dezena (igual para todas).")
    c5.metric("ID do conjunto", res["id"], help="Identifica este conjunto: depende do código do apostador e das âncoras.")

    aba_bloco, aba_arquivos = st.tabs(["🔎 Ver os jogos de um lote", "⬇️ Baixar os jogos do conjunto"])

    with aba_bloco:
        bloco = st.number_input(
            "Número do lote (1 a 593.775)",
            min_value=1,
            max_value=n.TOTAL_BLOCOS,
            value=1,
            step=1,
            key="numero_bloco",
            help="Apenas para consultar um lote na tela. Não altera o conjunto nem a conferência.",
        )
        colunas, jogos = n.gerar_blocos(ancoras, res["semente"], np.array([int(bloco) - 1]))
        legenda = " ".join(
            f'<b style="color:{CORES[k]};">N{c + 1}</b> ({ancoras[c][0]:02d}/{ancoras[c][1]:02d})'
            for k, c in enumerate(colunas[0])
        )
        st.markdown(f"Colunas do lote {int(bloco):06d}: {legenda}", unsafe_allow_html=True)
        st.caption(
            "Cada jogo tem 6 dezenas, da 1ª à 6ª posição. O cabeçalho mostra a posição e a coluna de origem "
            "(N1 a N30); a posição é a ordem da coluna dentro do lote (da menor para a maior). "
            "Os jogos não seguem ordem crescente."
        )
        st.markdown(html_bloco(colunas[0], jogos[0]), unsafe_allow_html=True)

    with aba_arquivos:
        st.write(
            f"O conjunto tem {milhar(n.TOTAL_JOGOS)} jogos, divididos em **{n.TOTAL_ARQUIVOS} arquivos CSV** de até "
            f"{milhar(n.BLOCOS_POR_ARQUIVO * n.JOGOS_POR_BLOCO)} jogos (cabem em uma planilha do Excel). "
            "Colunas: Lote, Jogo e D1 a D6 (as 6 dezenas do jogo, da 1ª à 6ª posição)."
        )
        formato = st.radio(
            "Como baixar",
            [f"ZIP com {n.ARQUIVOS_POR_ZIP} arquivos (recomendado)", "Um arquivo CSV"],
            horizontal=True,
            key="formato_download",
        )
        prefixo = f"senamatch_{res['codigo']}_{res['id']}"

        if formato == "Um arquivo CSV":

            def rotulo(num: int) -> str:
                ini, fim = n.intervalo_do_arquivo(num)
                return f"Arquivo {num:02d} de {n.TOTAL_ARQUIVOS} — lotes {milhar(ini + 1)} a {milhar(fim)}"

            numero = st.selectbox("Arquivo", range(1, n.TOTAL_ARQUIVOS + 1), format_func=rotulo, key="arquivo_escolhido")
            chave = (res["id"], "csv", numero)
            nome = f"{prefixo}_parte{numero:02d}de{n.TOTAL_ARQUIVOS}.csv"
            mime = "text/csv"
        else:

            def rotulo(num: int) -> str:
                arquivos = n.arquivos_do_zip(num)
                return f"Pacote {num} de {n.TOTAL_ZIPS} — arquivos {arquivos[0]:02d} a {arquivos[-1]:02d}"

            numero = st.selectbox("Pacote", range(1, n.TOTAL_ZIPS + 1), format_func=rotulo, key="zip_escolhido")
            chave = (res["id"], "zip", numero)
            nome = f"{prefixo}_pacote{numero}de{n.TOTAL_ZIPS}.zip"
            mime = "application/zip"
            st.caption(
                f"Cada pacote leva cerca de 10 segundos para ser preparado. "
                f"Baixe os {n.TOTAL_ZIPS} pacotes para ter o conjunto completo."
            )

        if st.button("Preparar download", key="btn_preparar"):
            if formato == "Um arquivo CSV":
                with st.spinner("Gerando o arquivo..."):
                    dados = n.gerar_csv(res["ancoras"], res["semente"], numero)
            else:
                barra = st.progress(0.0, text="Gerando o pacote...")
                dados = n.gerar_zip(
                    res["ancoras"],
                    res["semente"],
                    numero,
                    prefixo,
                    lambda feitos, total: barra.progress(feitos / total, text=f"Arquivo {feitos} de {total} do pacote"),
                )
                barra.empty()
            st.session_state["arquivo"] = {"chave": chave, "dados": dados, "nome": nome, "mime": mime}
        pronto = st.session_state.get("arquivo")
        if pronto and pronto["chave"] == chave:
            st.download_button(
                f"⬇️ Baixar {pronto['nome']} ({len(pronto['dados']) / 1e6:.1f} MB)",
                data=pronto["dados"],
                file_name=pronto["nome"],
                mime=pronto["mime"],
                key="btn_download",
            )


@st.cache_data(show_spinner=False, max_entries=4)
def resumir_sorteios(ancoras: list[list[int]], sorteios: list[tuple[int, ...]]) -> list[dict]:
    """Contagem por faixa e melhor resultado de cada sorteio (sem guardar a lista de jogos)."""
    return [n.resumir_sorteio(ancoras, sorteio) for sorteio in sorteios]


def mostrar_detalhes(indice: int, rotulo: str, sorteio: tuple[int, ...], res: dict) -> None:
    r = n.conferir_sorteio(res["ancoras"], res["semente"], sorteio)
    st.subheader(f"{rotulo} — {' '.join(f'{d:02d}' for d in sorteio)}")
    total_sorteio = len(r["acertos"])
    if not total_sorteio:
        st.write(f"Sem jogos premiados. Melhor resultado do conjunto: {r['melhor']} acerto(s).")
        return
    st.caption("Dezenas acertadas em destaque (bolinha cheia com brilho); as demais ficam apagadas.")
    exibir = min(total_sorteio, MAX_JOGOS_EXIBIDOS)
    st.markdown(
        "".join(
            html_jogo_conferido(int(r["blocos"][k]), int(r["jogos"][k]), r["dezenas"][k], sorteio)
            for k in range(exibir)
        ),
        unsafe_allow_html=True,
    )
    if total_sorteio > exibir:
        st.caption(f"Mostrando os {exibir} melhores de {milhar(total_sorteio)} jogos premiados.")
    tabela = pd.DataFrame(
        {
            "Faixa": [FAIXAS[int(a)] for a in r["acertos"]],
            "Acertos": r["acertos"],
            "Lote": r["blocos"],
            "Jogo": r["jogos"],
            **{f"D{c + 1}": r["dezenas"][:, c] for c in range(6)},
        }
    )
    st.download_button(
        f"⬇️ Baixar os {milhar(total_sorteio)} jogos premiados (CSV)",
        data=tabela.to_csv(sep=";", index=False).encode("utf-8-sig"),
        file_name=f"premiados_{rotulo.replace(' ', '_')}.csv",
        mime="text/csv",
        key=f"btn_premiados_{indice}",
    )


def mostrar_conferidor(res: dict) -> None:
    st.divider()
    st.header("✅ Conferidor de Resultados")
    st.caption(
        "Digite os sorteios da Sena, um por linha (6 dezenas, separadas por espaço, vírgula ou hífen). "
        "Opcionalmente, identifique o concurso antes de dois-pontos, "
        "ex.: Concurso 2800: 04 11 25 38 47 59. A conferência é automática "
        "(Ctrl+Enter ou clique fora do campo). Ela considera **o conjunto inteiro** "
        f"({milhar(n.TOTAL_BLOCOS)} lotes), independentemente do lote que você estiver visualizando. "
        f"Limite: {MAX_SORTEIOS} sorteios por vez."
    )
    texto = st.text_area(
        "Resultados dos sorteios",
        height=140,
        placeholder="Concurso 2800: 04 11 25 38 47 59\n05 17 23 31 42 60",
        key="texto_sorteios",
    )
    sorteios, erros = n.interpretar_sorteios(texto)
    for erro in erros:
        st.error(erro)
    if not sorteios:
        if not erros:
            st.info("Aguardando o resultado dos sorteios.")
        return
    if len(sorteios) > MAX_SORTEIOS:
        st.warning(f"Foram informados {len(sorteios)} sorteios; conferindo apenas os {MAX_SORTEIOS} primeiros.")
        sorteios = sorteios[:MAX_SORTEIOS]

    resumos = resumir_sorteios(res["ancoras"], [s for _, s in sorteios])
    totais = [sum(r["contagem"].values()) for r in resumos]

    total = sum(totais)
    if total:
        st.success(f"🎉 {milhar(total)} jogo(s) premiado(s) em {len(sorteios)} sorteio(s) conferido(s)!")
    else:
        st.warning(f"Nenhum jogo premiado (Quadra ou mais) em {len(sorteios)} sorteio(s) conferido(s).")

    tabela_resumo = pd.DataFrame(
        [
            {
                "Sorteio": rotulo,
                "Dezenas": " ".join(f"{d:02d}" for d in sorteio),
                **{FAIXAS[k]: r["contagem"][k] for k in FAIXAS},
                "Melhor resultado": f"{r['melhor']} acertos",
            }
            for (rotulo, sorteio), r in zip(sorteios, resumos)
        ]
    ).set_index("Sorteio")
    if len(sorteios) <= MAX_DETALHES:
        st.table(tabela_resumo)
    else:
        st.dataframe(tabela_resumo, height=min(35 * len(sorteios) + 38, 420))
        st.download_button(
            "⬇️ Baixar o resumo dos sorteios (CSV)",
            data=tabela_resumo.to_csv(sep=";").encode("utf-8-sig"),
            file_name="resumo_sorteios.csv",
            mime="text/csv",
            key="btn_resumo",
        )

    if len(sorteios) <= MAX_DETALHES:
        for i, (rotulo, sorteio) in enumerate(sorteios):
            mostrar_detalhes(i, rotulo, sorteio, res)
        return

    com_premio = [i for i, t in enumerate(totais) if t]
    if not com_premio:
        return
    st.caption(f"Com mais de {MAX_DETALHES} sorteios, os jogos premiados são mostrados um sorteio por vez.")
    escolhido = st.selectbox(
        "Ver os jogos premiados de",
        com_premio,
        format_func=lambda i: f"{sorteios[i][0]} — {' '.join(f'{d:02d}' for d in sorteios[i][1])} ({milhar(totais[i])} jogos)",
        key="sorteio_detalhe",
    )
    mostrar_detalhes(escolhido, sorteios[escolhido][0], sorteios[escolhido][1], res)


# ----------------------------------------------------------------------
# Interface
# ----------------------------------------------------------------------
LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.png")
st.set_page_config(
    page_title="SenaMatch",
    page_icon=LOGO if os.path.exists(LOGO) else "🎯",
    layout="wide",
)

# Streamlit renderiza no body; os navegadores costumam ignorar estas tags fora do <head>,
# então o nome/ícone do atalho depende principalmente de page_title e page_icon acima.
st.markdown(
    """
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-title" content="SenaMatch">
    <link rel="icon" href="app/static/logo.png">
    """,
    unsafe_allow_html=True,
)

segredo, segredo_seguro = obter_segredo()

with st.sidebar:
    st.title("Identificação")
    codigo_apostador = st.text_input("Código do Apostador Base", value="593775", key="codigo_apostador")
    if not segredo_seguro:
        st.warning(
            "Modo de desenvolvimento: defina SENAMATCH_SECRET para que os conjuntos "
            "sejam exclusivos e não reproduzíveis por terceiros."
        )

st.title("🎯 SenaMatch - Simulador de Lotes")
st.write(
    "Gerador exclusivo de jogos da Sena para o apostador base, a partir de 30 colunas "
    "com 2 dezenas âncora cada."
)
with st.expander("ℹ️ Como funciona: conjunto, lote e jogo", expanded=True):
    st.markdown(
        "- **Jogo:** 6 dezenas, uma de cada coluna do lote. A dezena fica na posição da sua coluna: "
        "as dezenas de **N1 ficam sempre na 1ª posição**, independente do valor, e as demais colunas "
        "ocupam a posição que têm dentro do lote (da menor para a maior). Os jogos não seguem ordem crescente.\n"
        f"- **Lote:** a escolha de 6 colunas entre as 30. Gera **{n.JOGOS_POR_BLOCO} jogos**: cada coluna "
        "contribui com as suas 2 dezenas, 32 vezes cada, em ordem sorteada (sem padrão alternado).\n"
        f"- **Conjunto:** todos os lotes do apostador: **{milhar(n.TOTAL_BLOCOS)} lotes**, "
        f"ou **{milhar(n.TOTAL_JOGOS)} jogos**. É o que você gera, baixa e confere.\n"
        "- O **código do apostador** e as **âncoras** definem a ordem dos lotes e dos jogos: "
        "mesmo código e mesmas âncoras sempre geram o mesmo conjunto."
    )

st.subheader("Configuração das Âncoras (30 Colunas / 2 Dezenas por Coluna)")
st.caption(
    "As 60 dezenas (01 a 60) devem ser todas diferentes, em qualquer ordem. Cada lote usa 6 colunas; "
    "de cada uma, as 2 dezenas aparecem 32 vezes cada, em ordem sorteada. "
    "Edite as células da tabela para mudar as âncoras."
)

if "versao_ancoras" not in st.session_state:
    st.session_state["versao_ancoras"] = 0
padrao = pd.DataFrame(
    n.PADRAO_ANCORAS,
    index=[f"N{c + 1}" for c in range(n.NUM_COLUNAS)],
    columns=["Dezena 1", "Dezena 2"],
).T.astype("Int64")
editado = st.data_editor(
    padrao,
    num_rows="fixed",
    width="stretch",
    column_config={
        f"N{c + 1}": st.column_config.NumberColumn(
            f"N{c + 1}", min_value=n.DEZENA_MIN, max_value=n.DEZENA_MAX, step=1, format="%02d", width=62
        )
        for c in range(n.NUM_COLUNAS)
    },
    key=f"ancoras_{st.session_state['versao_ancoras']}",
)
if st.button("Restaurar âncoras padrão", key="btn_restaurar"):
    st.session_state["versao_ancoras"] += 1
    st.rerun()

colunas_cfg = [
    [None if pd.isna(editado.iloc[j, c]) else int(editado.iloc[j, c]) for j in range(n.DEZENAS_POR_COLUNA)]
    for c in range(n.NUM_COLUNAS)
]
problemas = n.validar_ancoras(colunas_cfg)
for problema in problemas:
    st.error(problema)

st.divider()

if st.button(
    f"🚀 Gerar o Conjunto ({milhar(n.TOTAL_BLOCOS)} lotes · {milhar(n.TOTAL_JOGOS)} jogos)",
    type="primary",
    key="btn_gerar",
    disabled=bool(problemas),
):
    codigo = codigo_apostador.strip()
    if not codigo:
        st.error("Informe o Código do Apostador Base na barra lateral.")
    else:
        semente = n.criar_semente(segredo, codigo, colunas_cfg)
        # Guarda só a configuração: os jogos são gerados sob demanda a partir dela
        st.session_state["resultado"] = {
            "codigo": codigo,
            "ancoras": [list(c) for c in colunas_cfg],
            "semente": semente,
            "id": n.criar_id_lote(semente),
        }
        st.session_state.pop("arquivo", None)
        st.success(
            f"✅ Conjunto gerado para o apostador {codigo}: {milhar(n.TOTAL_BLOCOS)} lotes, "
            f"{milhar(n.TOTAL_JOGOS)} jogos. Use as abas abaixo para ver um lote ou baixar os jogos."
        )

resultado = st.session_state.get("resultado")
if resultado:
    if resultado["codigo"] != codigo_apostador.strip() or resultado["ancoras"] != colunas_cfg:
        st.info("As âncoras ou o código foram alterados. Clique em gerar para criar o novo conjunto.")
    mostrar_resultado(resultado)
    mostrar_conferidor(resultado)