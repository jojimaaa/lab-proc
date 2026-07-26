"""RF-01 — Interface para visualização da tradução.

Cenário da Tabela 1 do documento de arquitetura: "Conectando no HDMI do
Raspberry Pi, verificar o frontend" → "Carregamento correto do frontend,
sem falhas". Aqui o carregamento é verificado por cliente HTTP: a página
principal, os arquivos estáticos e as APIs que alimentam a interface.
"""
import pytest

from libras.monitor import PerformanceMonitor, machine_info
from libras.pipeline import PipelineState
from libras.server import create_app


@pytest.fixture()
def client():
    state = PipelineState()
    monitor = PerformanceMonitor()
    app = create_app(state.to_dict, monitor.sample, machine_info,
                     frame_provider=None)
    app.config["TESTING"] = True
    return app.test_client()


def test_pagina_principal_carrega_sem_falhas(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.content_type
    html = resp.get_data(as_text=True)
    assert "Tradutor Embarcado de LIBRAS" in html
    for element in ('id="traducao"', 'id="dashboard"', 'id="letra"',
                    'id="video"'):
        assert element in html, f"frontend sem o elemento {element}"


def test_arquivos_estaticos_servidos(client):
    assert client.get("/style.css").status_code == 200
    assert client.get("/app.js").status_code == 200


def test_api_de_estado_alimenta_a_interface(client):
    resp = client.get("/api/state")
    assert resp.status_code == 200
    data = resp.get_json()
    for key in ("letra_atual", "confianca", "palavra_parcial",
                "ultima_palavra", "historico", "fps", "mao_presente"):
        assert key in data, f"estado sem a chave {key}"


def test_api_de_metricas_alimenta_o_dashboard(client):
    resp = client.get("/api/metrics")
    assert resp.status_code == 200
    data = resp.get_json()
    for key in ("cpu_percent", "ram_percent", "clock_mhz", "temperatura_c",
                "cpi", "ipc"):
        assert key in data, f"métricas sem a chave {key}"


def test_api_de_info_da_maquina(client):
    data = client.get("/api/info").get_json()
    assert data["nucleos_logicos"] >= 1
    assert "processador" in data and "sistema" in data


def test_video_indisponivel_retorna_erro_claro(client):
    assert client.get("/video_feed").status_code == 503


def test_rota_inexistente_nao_derruba_o_servidor(client):
    assert client.get("/nao-existe").status_code == 404
    assert client.get("/").status_code == 200
