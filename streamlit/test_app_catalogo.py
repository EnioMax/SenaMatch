from pathlib import Path

import numpy as np
from streamlit.testing.v1 import AppTest

import catalogo_filtrado as cf
import nucleo as n


def test_interface_experimental_isolada(monkeypatch):
    monkeypatch.setenv("SENAMATCH_DEV", "1")
    monkeypatch.delenv("SENAMATCH_SECRET", raising=False)
    monkeypatch.setattr(n, "carregar_ancoras_padrao", lambda: n.PADRAO_ANCORAS)
    chamadas = []

    def catalogo_teste(ancoras, semente):
        chamadas.append((ancoras, semente))
        return cf.CatalogoExperimental(n.ancoras_para_array(ancoras), semente, np.arange(10, dtype=np.uint32))

    monkeypatch.setattr(cf, "criar_catalogo", catalogo_teste)
    app = AppTest.from_file(str(Path(__file__).with_name("app.py")), default_timeout=30).run()
    assert not app.exception
    app.button(key="gerar_experimental").click().run()
    assert any("30 pares" in aviso.value for aviso in app.error)
    assert not chamadas

    texto = "; ".join(f"N{i + 1}: {2 * i + 1:02d}, {2 * i + 2:02d}" for i in range(30))
    app.text_area(key="ancoras_experimentais").input(texto).run()
    app.button(key="gerar_experimental").click().run()
    assert not app.exception
    assert len(chamadas) == 1
    assert app.session_state["catalogo_experimental"].total_lotes == 2
    assert app.number_input(key="numero_lote_experimental").value == 1
    assert len(app.dataframe[-1].value) == 5

    app.number_input(key="numero_lote_experimental").set_value(2).run()
    assert not app.exception
    assert app.number_input(key="numero_lote_experimental").value == 2
    app.text_area(key="ancoras_experimentais").input(texto + "; N31: 01, 02").run()
    assert not app.exception
    assert "catalogo_experimental" not in app.session_state
