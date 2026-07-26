"""RNF-02 — Métricas de desempenho.

Cenário da Tabela 2 do documento de arquitetura: "No frontend, analisar o
dashboard do processador (CPI, taxa de clock etc.)" → "Comparar a
performance do projeto em diferentes hardwares". Validamos o monitor, sua
exposição via API e o benchmark comparável entre máquinas (Seção 7.5).
"""
import json
import time

import psutil
import pytest

from libras.benchmark import format_report, run_benchmark
from libras.monitor import PerformanceMonitor, machine_info
from libras.pipeline import PipelineState
from libras.server import create_app

ESSENTIAL_KEYS = ("cpu_percent", "cpu_por_nucleo", "ram_percent",
                  "ram_usada_mb", "ram_total_mb", "clock_mhz",
                  "temperatura_c", "cpi", "ipc")


@pytest.fixture(scope="module")
def benchmark_results():
    return run_benchmark(rapido=True)


def test_amostra_contem_todas_as_metricas_do_dashboard():
    sample = PerformanceMonitor().sample()
    for key in ESSENTIAL_KEYS:
        assert key in sample, f"métrica ausente: {key}"
    assert 0.0 <= sample["cpu_percent"] <= 100.0
    assert 0.0 <= sample["ram_percent"] <= 100.0
    assert len(sample["cpu_por_nucleo"]) == psutil.cpu_count(logical=True)
    if sample["clock_mhz"] is not None:
        assert sample["clock_mhz"] > 0
    if sample["temperatura_c"] is not None:
        assert -20.0 < sample["temperatura_c"] < 130.0
    if sample["cpi"] is not None:
        assert 0.05 < sample["cpi"] < 50.0


def test_informacoes_da_maquina_para_comparacao_entre_hardwares():
    info = machine_info()
    for key in ("hostname", "sistema", "arquitetura", "processador",
                "nucleos_fisicos", "nucleos_logicos", "python"):
        assert key in info, f"informação ausente: {key}"


def test_monitor_amostra_em_segundo_plano():
    monitor = PerformanceMonitor(interval=0.05)
    first = monitor.latest()  # amostra síncrona inicial
    monitor.start()
    try:
        deadline = time.time() + 3.0
        current = first
        while (time.time() < deadline
               and current["timestamp"] == first["timestamp"]):
            time.sleep(0.05)
            current = monitor.latest()
        assert current["timestamp"] > first["timestamp"], \
            "a thread de monitoramento não produziu novas amostras"
    finally:
        monitor.stop()


def test_metricas_expostas_ao_frontend_pela_api():
    monitor = PerformanceMonitor()
    app = create_app(PipelineState().to_dict, monitor.sample, machine_info)
    data = app.test_client().get("/api/metrics").get_json()
    for key in ESSENTIAL_KEYS:
        assert key in data, f"API sem a métrica {key}"


def test_benchmark_produz_resultado_comparavel(benchmark_results):
    assert benchmark_results["pontuacao"] > 0
    names = [c["nome"] for c in benchmark_results["cargas"]]
    assert names == ["inteiro_python", "flutuante_matmul", "memoria_copia",
                     "pipeline_traducao"]
    for load in benchmark_results["cargas"]:
        assert load["melhor_s"] > 0
        assert load["valor"] > 0
    json.dumps(benchmark_results)  # exportável p/ comparação entre máquinas


def test_relatorio_do_benchmark_cobre_cpi_e_clock(benchmark_results):
    report = format_report(benchmark_results)
    assert "CPI" in report
    assert "Clock" in report
    assert "PONTUAÇÃO" in report
