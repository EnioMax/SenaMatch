"""
SenaMatch - Simulador de Lotes (v4)

Regra do conjunto:
  - 30 colunas (N1..N30), cada uma com 2 dezenas âncora (as 60 dezenas, todas diferentes).
  - Um BLOCO é a escolha de 6 colunas entre as 30: C(30;6) = 593.775 blocos.
  - Cada bloco gera 2^6 = 64 jogos (1 dezena de cada coluna escolhida), sem repetição.
  - Total do conjunto: 593.775 x 64 = 38.001.600 jogos; cada dezena aparece no mesmo número de jogos.
  - Distribuição: os blocos formam 118.755 grupos de 5 (320 jogos), e cada grupo vira 64 lotes de
    5 jogos: 7.600.320 lotes. O jogo k (0..4) do lote m do grupo G vem da posição m do bloco
    5 x G' + (m + k) mod 5, com G' = (G + k x 23.751) mod 118.755. O jogo 1 fica no próprio grupo
    e os outros 4 são herdados de grupos diferentes. Nenhum jogo se repete. A regra é fixa (sem sorteio).
  - Cada jogo mostra as 6 dezenas em ordem crescente (menor à esquerda), como o resultado do sorteio.

O código do apostador e o segredo do servidor definem a ORDEM dos blocos e dos jogos
(HMAC). Mesmo código + mesmas âncoras -> sempre o mesmo conjunto.
Os jogos são gerados sob demanda e entregues em arquivos CSV (cabem no Excel).

Segredo: defina SENAMATCH_SECRET em st.secrets (Streamlit Cloud) ou como variável de ambiente.
O app não inicia sem ele; para testes locais use SENAMATCH_DEV=1.
"""

import os

import numpy as np
import pandas as pd
import streamlit as st

import caixa
import nucleo as n

FAIXAS = {6: "🏆 Sena", 5: "🥈 Quina", 4: "🥉 Quadra"}
MAX_JOGOS_EXIBIDOS = 200
LOTES_NA_TELA = 15
COLUNAS_NA_TELA = 3
MAX_SORTEIOS = 1000
MAX_DETALHES = 5  # até aqui mostra os jogos premiados de todos os sorteios
MAX_RANKING = 100  # lotes mostrados no ranking (o CSV leva todos)
VALOR_APOSTA_PADRAO = 6.00
FILTROS_PADRAO = {"filtro_faixas": list(FAIXAS), "filtro_lotes": "", "filtro_jogo": "Todos"}

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
    """Retorna (segredo, seguro). Sem segredo configurado, o app para (falha fechada).

    O modo de desenvolvimento só existe com SENAMATCH_DEV=1 no ambiente (nunca no deploy).
    """
    try:
        segredo = str(st.secrets["SENAMATCH_SECRET"])
    except Exception:
        segredo = os.environ.get("SENAMATCH_SECRET", "")
    if segredo:
        return segredo, True
    if os.environ.get("SENAMATCH_DEV") == "1":
        return "segredo-de-desenvolvimento", False
    st.error("Configuração incompleta: defina SENAMATCH_SECRET (Secrets do Streamlit ou variável de ambiente).")
    st.stop()


# ----------------------------------------------------------------------
# Exibição
# ----------------------------------------------------------------------
def html_bloco(colunas: np.ndarray, jogos: np.ndarray) -> str:
    """Os jogos de um lote (colunas e jogos: (5, 6)); cada bolinha mostra a coluna de origem ao passar o mouse."""
    celula = "padding:2px 4px;text-align:center;"
    bola = (
        "display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;"
        "border-radius:50%;font-weight:600;font-size:12px;color:#fff;box-sizing:border-box;"
    )
    cabecalho = "".join(
        f'<th style="{celula}font-size:11px;line-height:1.3;color:{CORES[k]};">D{k + 1}</th>' for k in range(6)
    )
    linhas = []
    for num, (jogo, cols) in enumerate(zip(jogos, colunas), start=1):
        celulas = "".join(
            f'<td style="{celula}"><span title="N{int(cols[k]) + 1}" style="{bola}background:{CORES[k]};">{int(d):02d}</span></td>'
            for k, d in enumerate(jogo)
        )
        linhas.append(f'<tr><td style="padding:2px 6px 2px 0;font-weight:600;white-space:nowrap;font-size:13px;">Jogo {num}</td>{celulas}</tr>')
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
        f'<span style="min-width:150px;font-weight:600;">Lote {bloco:07d} · Jogo {jogo}</span>{bolas}'
        f'<span style="margin-left:6px;"><b>{FAIXAS[len(acertos)]} · {len(acertos)} acertos</b>: {lista}</span></div>'
    )


def milhar(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


def reais(valor: float) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def mostrar_resultado(res: dict) -> None:
    ancoras = n.ancoras_para_array(res["ancoras"])

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Lotes no conjunto", milhar(n.TOTAL_LOTES), help="Cada lote tem 5 jogos.")
    c2.metric("Jogos por lote", n.JOGOS_POR_LOTE, help="Cada lote reúne 5 jogos do conjunto.")
    c3.metric("Jogos no conjunto", milhar(n.TOTAL_JOGOS), help="Todos os lotes juntos.")
    c4.metric("Jogos por dezena", milhar(n.JOGOS_POR_DEZENA), help="Quantos jogos do conjunto contêm cada dezena (igual para todas).")
    c5.metric("ID do conjunto", res["id"], help="Identifica este conjunto: depende do código do apostador e das âncoras.")

    aba_bloco, aba_arquivos = st.tabs(["🔎 Ver os jogos de um lote", "⬇️ Baixar os jogos do conjunto"])

    with aba_bloco:
        ultimo_inicio = n.TOTAL_LOTES - LOTES_NA_TELA + 1
        inicio = st.number_input(
            f"Lote inicial (1 a {milhar(ultimo_inicio)})",
            min_value=1,
            max_value=ultimo_inicio,
            value=1,
            step=LOTES_NA_TELA,
            key="numero_bloco",
            help=f"Mostra {LOTES_NA_TELA} lotes seguidos a partir deste. Apenas para consulta: não altera o conjunto nem a conferência.",
        )
        inicio = int(inicio)
        lotes_tela = np.arange(inicio - 1, inicio - 1 + LOTES_NA_TELA)
        colunas, jogos = n.gerar_lotes(ancoras, res["semente"], lotes_tela)
        st.markdown(
            f"**Lotes {inicio:07d} a {inicio + LOTES_NA_TELA - 1:07d}**: {LOTES_NA_TELA} lotes de {n.JOGOS_POR_LOTE} jogos"
        )
        st.caption(
            "O jogo 1 de cada lote vem do próprio grupo de blocos e os outros 4 são herdados de grupos "
            "diferentes, por um deslocamento fixo; nenhum jogo do conjunto se repete. "
            "Cada jogo tem 6 dezenas em "
            "ordem crescente (menor à esquerda); passe o mouse sobre uma dezena para ver a coluna de origem (N1 a N30)."
        )
        for linha in range(0, LOTES_NA_TELA, COLUNAS_NA_TELA):
            for coluna_st, i in zip(st.columns(COLUNAS_NA_TELA), range(linha, linha + COLUNAS_NA_TELA)):
                with coluna_st:
                    st.markdown(f"**Lote {inicio + i:07d}**")
                    st.markdown(html_bloco(colunas[i], jogos[i]), unsafe_allow_html=True)

    with aba_arquivos:
        st.write(
            f"O conjunto tem {milhar(n.TOTAL_JOGOS)} jogos, divididos em **{n.TOTAL_ARQUIVOS} arquivos CSV** de até "
            f"{milhar(n.LOTES_POR_ARQUIVO * n.JOGOS_POR_LOTE)} jogos (cabem em uma planilha do Excel). "
            "Colunas: Lote, Jogo e D1 a D6 (as 6 dezenas do jogo, em ordem crescente)."
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


@st.cache_data(show_spinner=False, max_entries=8)
def detalhar_sorteio(ancoras: list[list[int]], semente: int, sorteio: tuple[int, ...]) -> dict:
    """Jogos premiados do conjunto inteiro (em cache: mexer nos filtros não refaz a conferência)."""
    return n.conferir_sorteio(ancoras, semente, sorteio)


@st.cache_data(show_spinner="Conferindo os lotes escolhidos...", max_entries=2)
def detalhar_lotes(ancoras: list[list[int]], semente: int, lotes: np.ndarray, sorteios: list[tuple[int, ...]]) -> list[dict]:
    return n.conferir_lotes(ancoras, semente, lotes, sorteios)


def tabela_premiados(r: dict) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Faixa": [FAIXAS[int(a)] for a in r["acertos"]],
            "Acertos": r["acertos"],
            "Lote": r["blocos"],
            "Jogo": r["jogos"],
            **{f"D{c + 1}": r["dezenas"][:, c] for c in range(6)},
        }
    )


def csv_bytes(tabela: pd.DataFrame, indice: bool = False) -> bytes:
    return tabela.to_csv(sep=";", index=indice).encode("utf-8-sig")


def limpar_filtros() -> None:
    st.session_state.update(FILTROS_PADRAO)


def escolher_filtros() -> dict:
    """Filtros únicos da lista de jogos premiados, valem para todos os sorteios mostrados."""
    for chave, valor in FILTROS_PADRAO.items():
        st.session_state.setdefault(chave, valor)
    st.markdown("**🔍 Filtrar jogos premiados**")
    col_faixas, col_lotes, col_jogo, col_limpar = st.columns([2.2, 1.6, 1, 1], vertical_alignment="bottom")
    faixas = col_faixas.multiselect(
        "Faixas", options=list(FAIXAS), format_func=lambda acertos: FAIXAS[acertos], key="filtro_faixas"
    )
    texto_lotes = col_lotes.text_input(
        "Lotes (opcional)",
        placeholder="Ex.: 25, 100-200",
        key="filtro_lotes",
        help="Um lote, vários separados por vírgula ou faixas como 100-200.",
    )
    jogo = col_jogo.selectbox("Jogo", ["Todos", *range(1, n.JOGOS_POR_LOTE + 1)], key="filtro_jogo")
    col_limpar.button("Limpar filtros", key="btn_limpar_filtros", on_click=limpar_filtros, width="stretch")
    lotes, erros = n.interpretar_lotes(texto_lotes)
    for erro in erros:
        st.error(f"Filtro de lotes ignorado: {erro}")
    filtro = {
        "faixas": tuple(faixas),
        "lotes": lotes,
        "jogos": None if jogo == "Todos" else (int(jogo),),
    }
    filtro["ativo"] = set(faixas) != set(FAIXAS) or lotes is not None or filtro["jogos"] is not None
    st.caption("Os filtros valem para a lista exibida, o ranking e o CSV filtrado; o CSV completo continua disponível.")
    return filtro


def mostrar_detalhes(indice: int, rotulo: str, sorteio: tuple[int, ...], r: dict, filtro: dict, escopo: str) -> None:
    st.subheader(f"{rotulo} — {' '.join(f'{d:02d}' for d in sorteio)}")
    total_sorteio = len(r["acertos"])
    if not total_sorteio:
        st.write(f"Sem jogos premiados. Melhor resultado {escopo}: {r['melhor']} acerto(s).")
        return

    filtrados = n.filtrar_premiados(r, faixas=filtro["faixas"], lotes=filtro["lotes"], jogos=filtro["jogos"])
    total_filtrado = len(filtrados["acertos"])
    nome = n.nome_de_arquivo(rotulo)
    aba_jogos, aba_ranking = st.tabs(["🎯 Jogos premiados", "🏅 Ranking de lotes"])

    with aba_jogos:
        if not total_filtrado:
            st.info("Nenhum jogo premiado corresponde aos filtros selecionados.")
        exibir = min(total_filtrado, MAX_JOGOS_EXIBIDOS)
        if exibir:
            st.caption("Dezenas acertadas em destaque (bolinha cheia com brilho); as demais ficam apagadas.")
            st.markdown(
                "".join(
                    html_jogo_conferido(
                        int(filtrados["blocos"][k]), int(filtrados["jogos"][k]), filtrados["dezenas"][k], sorteio
                    )
                    for k in range(exibir)
                ),
                unsafe_allow_html=True,
            )
        if total_filtrado > exibir:
            st.caption(f"Mostrando os {exibir} melhores de {milhar(total_filtrado)} jogos que correspondem aos filtros.")
        st.download_button(
            f"⬇️ Baixar os {milhar(total_sorteio)} jogos premiados (CSV)",
            data=csv_bytes(tabela_premiados(r)),
            file_name=f"premiados_{nome}.csv",
            mime="text/csv",
            key=f"btn_premiados_{indice}",
        )
        if total_filtrado and filtro["ativo"]:
            st.download_button(
                f"⬇️ Baixar os {milhar(total_filtrado)} jogos filtrados (CSV)",
                data=csv_bytes(tabela_premiados(filtrados)),
                file_name=f"premiados_filtrados_{nome}.csv",
                mime="text/csv",
                key=f"btn_premiados_filtrados_{indice}",
            )

    with aba_ranking:
        ranking = n.ranking_por_lote(filtrados)
        if not len(ranking["lote"]):
            st.info("Nenhum lote premiado corresponde aos filtros selecionados.")
        else:
            tabela = pd.DataFrame(
                {
                    "Lote": ranking["lote"],
                    FAIXAS[6]: ranking["sena"],
                    FAIXAS[5]: ranking["quina"],
                    FAIXAS[4]: ranking["quadra"],
                    "Melhor resultado": ranking["melhor"],
                }
            )
            st.caption(
                f"{milhar(len(tabela))} lote(s) com jogos premiados, do que mais pontuou ao que menos "
                f"(Sena, depois Quina, depois Quadra). Mostrando os {min(len(tabela), MAX_RANKING)} primeiros."
            )
            st.dataframe(
                tabela.head(MAX_RANKING),
                hide_index=True,
                height=min(35 * min(len(tabela), MAX_RANKING) + 38, 420),
                column_config={"Lote": st.column_config.NumberColumn(format="%07d")},
            )
            st.download_button(
                f"⬇️ Baixar o ranking dos {milhar(len(tabela))} lotes (CSV)",
                data=csv_bytes(tabela),
                file_name=f"ranking_lotes_{nome}.csv",
                mime="text/csv",
                key=f"btn_ranking_{indice}",
            )


def buscar_concursos_caixa() -> None:
    """Preenche a caixa de sorteios com os últimos concursos da Caixa e guarda os prêmios por ganhador."""
    col_qtd, col_botao, _ = st.columns([1, 1.4, 3], vertical_alignment="bottom")
    quantidade = col_qtd.number_input(
        "Últimos concursos", min_value=1, max_value=caixa.MAX_CONCURSOS, value=5, step=1, key="qtd_caixa"
    )
    if not col_botao.button(
        "📥 Buscar da Caixa",
        key="btn_caixa",
        help="Consulta os resultados oficiais da Mega-Sena e já os confere (substitui o texto atual).",
    ):
        return
    with st.spinner("Consultando a Caixa..."):
        concursos, falhas = caixa.buscar_ultimos(int(quantidade))
    if not concursos:
        st.error("Não foi possível consultar a Caixa agora. Digite os sorteios manualmente.")
        return
    linhas, premios = [], {}
    for c in reversed(concursos):
        rotulo = f"Concurso {c['numero']}" + (f" ({c['data']})" if c["data"] else "")
        linhas.append(f"{rotulo}: {' '.join(f'{d:02d}' for d in c['dezenas'])}")
        premios[rotulo] = c["premios"]
    st.session_state["texto_sorteios"] = "\n".join(linhas)
    st.session_state["premios_caixa"] = premios
    if falhas:
        st.warning(f"{falhas} concurso(s) não puderam ser lidos e ficaram de fora.")


def escolher_lotes() -> tuple[np.ndarray | None, bool]:
    """Escopo da conferência: (lotes 0-based ou None para o conjunto inteiro, se já pode conferir)."""
    escopo = st.radio(
        "O que conferir",
        ["Conjunto inteiro", "Só os lotes que eu joguei"],
        horizontal=True,
        key="escopo_conferencia",
    )
    if escopo == "Conjunto inteiro":
        return None, True
    texto = st.text_input(
        "Lotes que você jogou",
        placeholder="Ex.: 25, 100-200, 1.000",
        key="lotes_jogados",
        help=f"Lotes avulsos separados por vírgula e faixas como 100-200 (até {milhar(n.MAX_LOTES_SELECIONADOS)} lotes).",
    )
    lotes, erros = n.interpretar_lotes(texto)
    for erro in erros:
        st.error(erro)
    if lotes is None:
        if not erros:
            st.info("Informe os lotes que você jogou para conferi-los.")
        return None, False
    st.caption(f"{milhar(len(lotes))} lote(s) selecionado(s), {milhar(len(lotes) * n.JOGOS_POR_LOTE)} jogos.")
    return lotes, True


def mostrar_conferidor(res: dict) -> None:
    st.divider()
    st.header("✅ Conferidor de Resultados")
    st.caption(
        "Digite os sorteios da Sena, um por linha (6 dezenas, separadas por espaço, vírgula ou hífen), "
        "ou busque os últimos concursos da Caixa. Opcionalmente, identifique o concurso antes de dois-pontos, "
        "ex.: Concurso 2800: 04 11 25 38 47 59. Clique em **Conferir** (ou use Ctrl+Enter) para ver o resultado. "
        "A conferência considera **o conjunto inteiro**, "
        "independentemente do lote que você estiver visualizando, ou só os lotes que você jogou. "
        f"Limite: {MAX_SORTEIOS} sorteios por vez."
    )
    lotes, pronto = escolher_lotes()
    buscar_concursos_caixa()
    with st.form("form_sorteios", border=False):
        texto = st.text_area(
            "Resultados dos sorteios",
            height=140,
            placeholder="Concurso 2800: 04 11 25 38 47 59\n05 17 23 31 42 60",
            key="texto_sorteios",
        )
        st.form_submit_button("✅ Conferir", type="primary", key="btn_conferir")
    sorteios, erros = n.interpretar_sorteios(texto)
    for erro in erros:
        st.error(erro)
    if not sorteios:
        if not erros:
            st.info("Aguardando o resultado dos sorteios.")
        return
    sorteios, repetidos = n.rotulos_unicos(sorteios)
    if repetidos:
        st.warning(f"Rótulos repetidos ({', '.join(repetidos)}): numerei os repetidos para diferenciá-los.")
    if len(sorteios) > MAX_SORTEIOS:
        st.warning(f"Foram informados {len(sorteios)} sorteios; conferindo apenas os {MAX_SORTEIOS} primeiros.")
        sorteios = sorteios[:MAX_SORTEIOS]
    st.caption(f"{len(sorteios)} sorteio(s) válido(s).")
    if not pronto:
        return

    ancoras, semente = res["ancoras"], res["semente"]
    dezenas = [s for _, s in sorteios]
    resumos = resumir_sorteios(ancoras, dezenas)
    if lotes is None:
        detalhes_lotes = None
        contagens = [r["contagem"] for r in resumos]
        melhores = [r["melhor"] for r in resumos]
        jogos_conferidos, escopo = n.TOTAL_JOGOS, "do conjunto"
    else:
        detalhes_lotes = detalhar_lotes(ancoras, semente, lotes, dezenas)
        contagens = [d["contagem"] for d in detalhes_lotes]
        melhores = [d["melhor"] for d in detalhes_lotes]
        jogos_conferidos, escopo = len(lotes) * n.JOGOS_POR_LOTE, "dos lotes escolhidos"
    totais = [sum(c.values()) for c in contagens]
    total = sum(totais)

    if total:
        st.success(f"🎉 {milhar(total)} jogo(s) premiado(s) em {len(sorteios)} sorteio(s) conferido(s)!")
    else:
        st.warning(f"Nenhum jogo premiado (Quadra ou mais) em {len(sorteios)} sorteio(s) conferido(s).")

    colunas_resumo = st.columns(4)
    for coluna, faixa in zip(colunas_resumo, FAIXAS):
        coluna.metric(FAIXAS[faixa], milhar(sum(c[faixa] for c in contagens)))
    if total and len(sorteios) > 1:
        melhor_i = max(range(len(sorteios)), key=lambda i: (contagens[i][6], contagens[i][5], contagens[i][4]))
        colunas_resumo[3].metric(
            "Melhor sorteio", sorteios[melhor_i][0], help="O sorteio com mais Senas, depois Quinas, depois Quadras."
        )

    retornos = mostrar_retorno_financeiro(sorteios, contagens, jogos_conferidos)

    tabela_resumo = pd.DataFrame(
        [
            {
                "Sorteio": rotulo,
                "Dezenas": " ".join(f"{d:02d}" for d in sorteio),
                **{FAIXAS[k]: contagens[i][k] for k in FAIXAS},
                "Melhor resultado": f"{melhores[i]} acertos",
                "Pares na mesma coluna": resumos[i]["cobertura"]["duplos"],
                **(
                    {"Prêmio": reais(retornos[i]["premio"]), "Saldo": reais(retornos[i]["saldo"])}
                    if retornos[i]
                    else ({"Prêmio": "—", "Saldo": "—"} if any(retornos) else {})
                ),
            }
            for i, (rotulo, sorteio) in enumerate(sorteios)
        ]
    ).set_index("Sorteio")
    if len(sorteios) <= MAX_DETALHES:
        st.table(tabela_resumo)
    else:
        st.dataframe(tabela_resumo, height=min(35 * len(sorteios) + 38, 420))
        st.download_button(
            "⬇️ Baixar o resumo dos sorteios (CSV)",
            data=csv_bytes(tabela_resumo, indice=True),
            file_name="resumo_sorteios.csv",
            mime="text/csv",
            key="btn_resumo",
        )
    st.caption(
        "**Pares na mesma coluna:** duas dezenas sorteadas na mesma coluna nunca aparecem juntas em um jogo. "
        "Com 0 pares, o conjunto inteiro contém uma Sena; cada par reduz em 1 o melhor resultado possível do conjunto (6 − pares)."
    )

    if total and len(sorteios) > 1:
        with st.expander("📊 Gráfico por sorteio", expanded=True):
            faixa = st.radio(
                "Faixa do gráfico",
                list(FAIXAS)[::-1],
                index=1,
                format_func=lambda acertos: FAIXAS[acertos],
                horizontal=True,
                key="faixa_grafico",
            )
            st.bar_chart(
                pd.DataFrame({FAIXAS[faixa]: [c[faixa] for c in contagens]}, index=[r for r, _ in sorteios]),
                sort=False,
            )

    com_premio = [i for i, t in enumerate(totais) if t]
    if not com_premio:
        if len(sorteios) <= MAX_DETALHES:
            for i, (rotulo, sorteio) in enumerate(sorteios):
                st.write(f"**{rotulo}** — sem jogos premiados. Melhor resultado {escopo}: {melhores[i]} acerto(s).")
        return

    def detalhe_de(i: int) -> dict:
        return detalhar_sorteio(ancoras, semente, sorteios[i][1]) if lotes is None else detalhes_lotes[i]

    filtro = escolher_filtros()
    if len(sorteios) <= MAX_DETALHES:
        for i, (rotulo, sorteio) in enumerate(sorteios):
            mostrar_detalhes(i, rotulo, sorteio, detalhe_de(i), filtro, escopo)
        return

    st.caption(f"Com mais de {MAX_DETALHES} sorteios, os jogos premiados são mostrados um sorteio por vez.")
    escolhido = st.selectbox(
        "Ver os jogos premiados de",
        com_premio,
        format_func=lambda i: f"{sorteios[i][0]} — {' '.join(f'{d:02d}' for d in sorteios[i][1])} ({milhar(totais[i])} jogos)",
        key="sorteio_detalhe",
    )
    mostrar_detalhes(escolhido, sorteios[escolhido][0], sorteios[escolhido][1], detalhe_de(escolhido), filtro, escopo)


def mostrar_retorno_financeiro(
    sorteios: list[tuple[str, tuple[int, ...]]], contagens: list[dict], jogos: int
) -> list[dict | None]:
    """Prêmio, investimento e saldo por sorteio (None onde não há valores de prêmio) e o total geral."""
    with st.expander("💰 Retorno financeiro (opcional)"):
        valor_aposta = st.number_input(
            "Valor de cada jogo (R$)", min_value=0.0, value=VALOR_APOSTA_PADRAO, step=0.5, format="%.2f", key="valor_aposta"
        )
        st.caption(
            "Os concursos buscados da Caixa já trazem o prêmio por ganhador. Para os sorteios digitados à mão, "
            "informe abaixo os valores (deixe 0 para ignorar)."
        )
        col6, col5, col4 = st.columns(3)
        manuais = {
            faixa: coluna.number_input(
                f"{FAIXAS[faixa]} (R$ por ganhador)", min_value=0.0, value=0.0, step=100.0, format="%.2f", key=f"premio_{faixa}"
            )
            for faixa, coluna in zip(FAIXAS, (col6, col5, col4))
        }
        da_caixa = st.session_state.get("premios_caixa", {})
        retornos: list[dict | None] = []
        for (rotulo, _), contagem in zip(sorteios, contagens):
            premios = da_caixa.get(rotulo) or (manuais if any(manuais.values()) else None)
            retornos.append(n.calcular_retorno(contagem, premios, jogos, valor_aposta) if premios else None)
        validos = [r for r in retornos if r]
        if not validos:
            return retornos
        premio = sum(r["premio"] for r in validos)
        investido = sum(r["investido"] for r in validos)
        saldo = premio - investido
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Prêmio total", reais(premio))
        c2.metric("Investido", reais(investido), help=f"{milhar(jogos)} jogo(s) por sorteio.")
        c3.metric("Saldo", reais(saldo))
        c4.metric("Retorno", f"{saldo / investido * 100:+.1f}%" if investido else "—")
        st.caption(
            f"Considera {len(validos)} de {len(sorteios)} sorteio(s) com prêmios conhecidos. Valores por ganhador: "
            "se o concurso acumulou (sem ganhador da Sena), a faixa vem zerada e o rateio real mudaria com os seus jogos. "
            "No conjunto inteiro o investimento é enorme; o retorno faz mais sentido conferindo só os lotes que você jogou."
        )
    return retornos


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
            "Modo de desenvolvimento (SENAMATCH_DEV=1): defina SENAMATCH_SECRET para que os conjuntos "
            "sejam exclusivos e não reproduzíveis por terceiros."
        )

st.title("🎯 SenaMatch - Simulador de Lotes")
st.write(
    "Gerador exclusivo de jogos da Sena para o apostador base, a partir de 30 colunas "
    "com 2 dezenas âncora cada."
)
with st.expander("ℹ️ Como funciona: conjunto, lote e jogo", expanded=True):
    st.markdown(
        "- **Jogo:** 6 dezenas, uma de cada coluna do bloco, exibidas em ordem crescente "
        "(menor à esquerda), como o resultado do sorteio.\n"
        f"- **Bloco:** a escolha de 6 colunas entre as 30. Gera **{n.JOGOS_POR_BLOCO} jogos**: cada coluna "
        "contribui com as suas 2 dezenas, 32 vezes cada.\n"
        f"- **Lote:** {n.JOGOS_POR_LOTE} jogos. Os blocos são agrupados de 5 em 5 e cada grupo forma 64 lotes: "
        "o 1º jogo do lote é do próprio grupo e cada um dos outros 4 é herdado de um grupo diferente, "
        "por um deslocamento fixo. Nenhum jogo se repete.\n"
        f"- **Conjunto:** todos os lotes do apostador: **{milhar(n.TOTAL_LOTES)} lotes**, "
        f"ou **{milhar(n.TOTAL_JOGOS)} jogos**. É o que você gera, baixa e confere.\n"
        "- O **código do apostador** e as **âncoras** definem a ordem dos blocos e dos jogos: "
        "mesmo código e mesmas âncoras sempre geram o mesmo conjunto."
    )

st.subheader("Configuração das Âncoras (30 Colunas / 2 Dezenas por Coluna)")
st.caption(
    "As 60 dezenas (01 a 60) devem ser todas diferentes, em qualquer ordem. Cada jogo usa 6 colunas; "
    "de cada uma, as 2 dezenas aparecem 32 vezes cada, em ordem sorteada. "
    "Edite as células da tabela para definir as âncoras: use **Limpar** para começar do zero e "
    "preencher as 60 dezenas. Com as 60 dezenas válidas, **Definir como padrão** as guarda como o padrão do app; "
    "ao recarregar a página, a tabela volta ao padrão atual."
)

if "versao_ancoras" not in st.session_state:
    st.session_state["versao_ancoras"] = 0
    st.session_state["ancoras_vazias"] = False


def limpar_ancoras() -> None:
    """Descarta as edições e recarrega a tabela vazia, para o usuário preencher as 60 dezenas."""
    st.session_state["ancoras_vazias"] = True
    st.session_state["versao_ancoras"] += 1


ancoras_padrao = n.carregar_ancoras_padrao()
padrao_personalizado = ancoras_padrao != n.PADRAO_ANCORAS
base = ancoras_padrao if not st.session_state["ancoras_vazias"] else [[None, None]] * n.NUM_COLUNAS
if aviso := st.session_state.pop("aviso_padrao", None):
    st.success(aviso)
padrao = pd.DataFrame(
    base,
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

colunas_cfg = [
    [None if pd.isna(editado.iloc[j, c]) else int(editado.iloc[j, c]) for j in range(n.DEZENAS_POR_COLUNA)]
    for c in range(n.NUM_COLUNAS)
]
problemas = n.validar_ancoras(colunas_cfg)
preenchidas = sum(d is not None for col in colunas_cfg for d in col)
if preenchidas < n.NUM_COLUNAS * n.DEZENAS_POR_COLUNA:
    st.caption(f"Dezenas preenchidas: {preenchidas} de {n.NUM_COLUNAS * n.DEZENAS_POR_COLUNA}.")
for problema in problemas:
    st.error(problema)

botao_definir, botao_limpar, botao_original = st.columns([1, 1, 1.6])
botao_limpar.button("Limpar", key="btn_limpar", on_click=limpar_ancoras, width="stretch")
if botao_definir.button(
    "Definir como padrão",
    key="btn_definir_padrao",
    disabled=bool(problemas),
    width="stretch",
    help="Guarda as âncoras da tabela como o padrão do app (vale para todos os usuários).",
):
    try:
        n.salvar_ancoras_padrao(colunas_cfg)
    except OSError:
        st.error("Não foi possível gravar o padrão no servidor.")
    else:
        st.session_state["ancoras_vazias"] = False
        st.session_state["versao_ancoras"] += 1
        st.session_state["aviso_padrao"] = "✅ Âncoras definidas como o novo padrão."
        st.rerun()
if padrao_personalizado and botao_original.button(
    "Voltar ao padrão original (01 a 60)", key="btn_padrao_original", width="stretch"
):
    try:
        n.remover_ancoras_padrao()
    except OSError:
        st.error("Não foi possível remover o padrão personalizado.")
    else:
        st.session_state["ancoras_vazias"] = False
        st.session_state["versao_ancoras"] += 1
        st.session_state["aviso_padrao"] = "✅ Padrão original (01 a 60) restaurado."
        st.rerun()

st.divider()

if st.button(
    f"🚀 Gerar o Conjunto ({milhar(n.TOTAL_LOTES)} lotes · {milhar(n.TOTAL_JOGOS)} jogos)",
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
            f"✅ Conjunto gerado para o apostador {codigo}: {milhar(n.TOTAL_LOTES)} lotes, "
            f"{milhar(n.TOTAL_JOGOS)} jogos. Use as abas abaixo para ver um lote ou baixar os jogos."
        )

resultado = st.session_state.get("resultado")
if resultado:
    if resultado["codigo"] != codigo_apostador.strip() or resultado["ancoras"] != colunas_cfg:
        st.info("As âncoras ou o código foram alterados. Clique em gerar para criar o novo conjunto.")
    mostrar_resultado(resultado)
    mostrar_conferidor(resultado)