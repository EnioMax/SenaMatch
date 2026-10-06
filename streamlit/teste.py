"""
SenaMatch - Simulador de Lotes (v4)

Regra do lote:
  - 30 colunas (N1..N30), cada uma com 2 dezenas âncora (as 60 dezenas, todas diferentes).
  - Um BLOCO é a escolha de 6 colunas entre as 30: C(30;6) = 593.775 blocos.
  - Cada bloco gera 2^6 = 64 jogos (1 dezena de cada coluna escolhida), sem repetição.
  - Total: 593.775 x 64 = 38.001.600 jogos; cada dezena aparece no mesmo número de jogos.

O código do apostador e o segredo do servidor definem a ORDEM dos blocos e dos jogos
(HMAC). Mesmo código + mesmas âncoras -> sempre o mesmo lote.
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

# Uma cor por posição de coluna dentro do bloco (tons que funcionam em tema claro e escuro)
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
def html_bloco(colunas: np.ndarray, jogos: np.ndarray, ancoras: np.ndarray) -> str:
    """Os 64 jogos de um bloco; a cor de cada dezena indica a coluna de origem."""
    cor_da_dezena = {int(d): CORES[k] for k, c in enumerate(colunas) for d in ancoras[c]}
    linhas = []
    for num, jogo in enumerate(jogos, start=1):
        bolas = "".join(
            f'<span style="{ESTILO_BOLA}background:{cor_da_dezena[int(d)]};color:#fff;">{int(d):02d}</span>'
            for d in jogo
        )
        linhas.append(
            '<div style="display:flex;align-items:center;gap:6px;margin:4px 0;">'
            f'<span style="min-width:70px;font-weight:600;">Jogo {num:02d}</span>{bolas}</div>'
        )
    return (
        '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));'
        'column-gap:24px;">' + "".join(linhas) + "</div>"
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
        f'<span style="min-width:150px;font-weight:600;">Bloco {bloco:06d} · Jogo {jogo:02d}</span>{bolas}'
        f'<span style="margin-left:6px;"><b>{FAIXAS[len(acertos)]} · {len(acertos)} acertos</b>: {lista}</span></div>'
    )


def mostrar_resultado(res: dict) -> None:
    ancoras = n.ancoras_para_array(res["ancoras"])

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Blocos (6 de 30 colunas)", f"{n.TOTAL_BLOCOS:,}".replace(",", "."))
    c2.metric("Jogos por bloco", n.JOGOS_POR_BLOCO)
    c3.metric("Total de jogos", f"{n.TOTAL_JOGOS:,}".replace(",", "."))
    c4.metric("Jogos por dezena", f"{n.JOGOS_POR_DEZENA:,}".replace(",", "."))
    c5.metric("ID do lote", res["id"])

    aba_bloco, aba_arquivos = st.tabs(["🎨 Visualizar um bloco", "⬇️ Baixar arquivos"])

    with aba_bloco:
        bloco = st.number_input(
            "Número do bloco",
            min_value=1,
            max_value=n.TOTAL_BLOCOS,
            value=1,
            step=1,
            key="numero_bloco",
        )
        colunas, jogos = n.gerar_blocos(ancoras, res["semente"], np.array([int(bloco) - 1]))
        legenda = " ".join(
            f'<b style="color:{CORES[k]};">N{c + 1}</b> ({ancoras[c][0]:02d}/{ancoras[c][1]:02d})'
            for k, c in enumerate(colunas[0])
        )
        st.markdown(f"Colunas do bloco {int(bloco):06d}: {legenda}", unsafe_allow_html=True)
        st.caption("Cada jogo usa 1 dezena de cada coluna do bloco; a cor indica a coluna de origem.")
        st.markdown(html_bloco(colunas[0], jogos[0], ancoras), unsafe_allow_html=True)

    with aba_arquivos:
        st.write(
            f"O lote tem {n.TOTAL_JOGOS:,} jogos".replace(",", ".")
            + f" e foi dividido em **{n.TOTAL_ARQUIVOS} arquivos CSV** de até "
            + f"{n.BLOCOS_POR_ARQUIVO * n.JOGOS_POR_BLOCO:,} jogos".replace(",", ".")
            + " (cabem em uma planilha do Excel). Colunas: Bloco, Jogo, Colunas do bloco e D1 a D6."
        )

        def rotulo(num: int) -> str:
            ini, fim = n.intervalo_do_arquivo(num)
            return f"Arquivo {num:02d} de {n.TOTAL_ARQUIVOS} — blocos {ini + 1:,} a {fim:,}".replace(",", ".")

        numero = st.selectbox("Arquivo", range(1, n.TOTAL_ARQUIVOS + 1), format_func=rotulo, key="arquivo_escolhido")
        chave = (res["id"], numero)
        if st.button("Preparar arquivo", key="btn_preparar"):
            with st.spinner("Gerando o arquivo..."):
                st.session_state["arquivo"] = {
                    "chave": chave,
                    "dados": n.gerar_csv(res["ancoras"], res["semente"], numero),
                    "nome": f"senamatch_{res['codigo']}_{res['id']}_parte{numero:02d}de{n.TOTAL_ARQUIVOS}.csv",
                }
        pronto = st.session_state.get("arquivo")
        if pronto and pronto["chave"] == chave:
            st.download_button(
                f"⬇️ Baixar {pronto['nome']} ({len(pronto['dados']) / 1e6:.1f} MB)",
                data=pronto["dados"],
                file_name=pronto["nome"],
                mime="text/csv",
                key="btn_download",
            )


def mostrar_conferidor(res: dict) -> None:
    st.divider()
    st.header("✅ Conferidor de Resultados")
    st.caption(
        "Digite os sorteios da Sena, um por linha (6 dezenas, separadas por espaço, vírgula ou hífen). "
        "Opcionalmente, identifique o concurso antes de dois-pontos, "
        "ex.: Concurso 2800: 04 11 25 38 47 59. A conferência é automática "
        "(Ctrl+Enter ou clique fora do campo) e considera todos os jogos do lote."
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

    resultados = [n.conferir_sorteio(res["ancoras"], res["semente"], s) for _, s in sorteios]

    total = sum(len(r["acertos"]) for r in resultados)
    if total:
        st.success(f"🎉 {total:,} jogo(s) premiado(s) em {len(sorteios)} sorteio(s) conferido(s)!".replace(",", "."))
    else:
        st.warning(f"Nenhum jogo premiado (Quadra ou mais) em {len(sorteios)} sorteio(s) conferido(s).")

    resumo = [
        {
            "Sorteio": rotulo,
            "Dezenas": " ".join(f"{d:02d}" for d in sorteio),
            **{FAIXAS[k]: r["contagem"][k] for k in FAIXAS},
            "Melhor resultado": f"{r['melhor']} acertos",
        }
        for (rotulo, sorteio), r in zip(sorteios, resultados)
    ]
    st.table(pd.DataFrame(resumo).set_index("Sorteio"))

    for i, ((rotulo, sorteio), r) in enumerate(zip(sorteios, resultados)):
        st.subheader(f"{rotulo} — {' '.join(f'{d:02d}' for d in sorteio)}")
        total_sorteio = len(r["acertos"])
        if not total_sorteio:
            st.write(f"Sem jogos premiados. Melhor resultado do lote: {r['melhor']} acerto(s).")
            continue
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
            st.caption(f"Mostrando os {exibir} melhores de {total_sorteio:,} jogos premiados.".replace(",", "."))
        tabela = pd.DataFrame(
            {
                "Faixa": [FAIXAS[int(a)] for a in r["acertos"]],
                "Acertos": r["acertos"],
                "Bloco": r["blocos"],
                "Jogo": r["jogos"],
                **{f"D{c + 1}": r["dezenas"][:, c] for c in range(6)},
            }
        )
        st.download_button(
            f"⬇️ Baixar os {total_sorteio:,} jogos premiados (CSV)".replace(",", "."),
            data=tabela.to_csv(sep=";", index=False).encode("utf-8-sig"),
            file_name=f"premiados_{rotulo.replace(' ', '_')}.csv",
            mime="text/csv",
            key=f"btn_premiados_{i}",
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
    "Gerador exclusivo de blocos de 64 jogos: cada bloco combina 6 das 30 colunas "
    "(2 dezenas por coluna) para o apostador base."
)

st.subheader("Configuração das Âncoras (30 Colunas / 2 Dezenas por Coluna)")
st.caption(
    "As 60 dezenas (01 a 60) devem ser todas diferentes. Cada bloco usa 6 colunas e, de cada uma, "
    "as 2 dezenas se alternam (32 jogos cada). Edite as células da tabela para mudar as âncoras."
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
    f"🚀 Gerar Lote Exclusivo ({n.TOTAL_BLOCOS:,} blocos de 64 jogos)".replace(",", "."),
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
        st.success(f"✅ Lote de {n.TOTAL_JOGOS:,} jogos gerado com sucesso para o apostador {codigo}!".replace(",", "."))

resultado = st.session_state.get("resultado")
if resultado:
    if resultado["codigo"] != codigo_apostador.strip() or resultado["ancoras"] != colunas_cfg:
        st.info("As âncoras ou o código foram alterados. Clique em gerar para criar o novo lote.")
    mostrar_resultado(resultado)
    mostrar_conferidor(resultado)
