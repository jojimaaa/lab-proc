"""RNF-03 — Portabilidade.

Cenário da Tabela 2 do documento de arquitetura: "dispositivo leve, pequeno
e robusto, sem gargalos de desempenho". Traduzido para software: o sistema é
autocontido (computação de borda, Seção 7.1) — roda sem as dependências de
hardware instaladas, sem qualquer acesso à rede externa e com uso de memória
estável em execução prolongada.
"""
import ast
import socket
from pathlib import Path

import psutil

import libras
from libras.demo import make_demo_components
from libras.monitor import PerformanceMonitor, machine_info
from libras.pipeline import PipelineState, TranslationPipeline
from libras.server import create_app

PACKAGE_DIR = Path(libras.__file__).resolve().parent
HARDWARE_DEPS = {"cv2", "mediapipe", "pyttsx3"}


def _module_level_imports(tree: ast.Module) -> set:
    """Nomes importados no nível do módulo (fora de funções/métodos)."""
    found = set()

    def visit(stmts):
        for node in stmts:
            if isinstance(node, ast.Import):
                found.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module.split(".")[0])
            elif isinstance(node, ast.If):
                visit(node.body)
                visit(node.orelse)
            elif isinstance(node, ast.Try):
                visit(node.body)
                visit(node.orelse)
                visit(node.finalbody)
                for handler in node.handlers:
                    visit(handler.body)

    visit(tree.body)
    return found


def test_sem_dependencia_rigida_de_hardware_no_import():
    """cv2/mediapipe/pyttsx3 devem ser importados tardiamente (dentro de
    funções), para o sistema degradar graciosamente onde eles não existem."""
    for source_file in sorted(PACKAGE_DIR.glob("*.py")):
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        rigid = _module_level_imports(tree) & HARDWARE_DEPS
        assert not rigid, (
            f"{source_file.name} importa {rigid} no nível do módulo")


def test_pipeline_completo_roda_sem_hardware(fast_config):
    """O núcleo inteiro funciona em uma máquina sem webcam/OpenCV/MediaPipe."""
    source, extractor, classifier = make_demo_components(fast_config)
    pipeline = TranslationPipeline(source, extractor, classifier,
                                   fast_config, state=PipelineState())
    for _ in range(20):
        assert pipeline.step()


def test_sistema_funciona_totalmente_offline(fast_config, monkeypatch):
    """Computação de borda: nenhum estágio pode depender de rede externa."""
    def block(*args, **kwargs):
        raise AssertionError("tentativa de acesso à rede detectada")

    monkeypatch.setattr(socket.socket, "connect", block)
    monkeypatch.setattr(socket.socket, "sendto", block, raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", block)

    source, extractor, classifier = make_demo_components(fast_config)
    state = PipelineState()
    pipeline = TranslationPipeline(source, extractor, classifier,
                                   fast_config, state=state)
    for _ in range(30):
        pipeline.step()

    monitor = PerformanceMonitor()
    app = create_app(state.to_dict, monitor.sample, machine_info)
    client = app.test_client()
    assert client.get("/").status_code == 200
    assert client.get("/api/state").status_code == 200
    assert client.get("/api/metrics").status_code == 200


def test_uso_de_memoria_estavel_em_execucao_prolongada(fast_config):
    """Execução contínua sem vazamento que inviabilize o embarcado."""
    source, extractor, classifier = make_demo_components(fast_config)
    pipeline = TranslationPipeline(source, extractor, classifier,
                                   fast_config, state=PipelineState())
    process = psutil.Process()
    for _ in range(50):        # aquecimento (buffers e caches internos)
        pipeline.step()
    rss_before = process.memory_info().rss
    for _ in range(500):
        pipeline.step()
    growth_mb = (process.memory_info().rss - rss_before) / 2**20
    # Crescimento real medido é ~0,02 MiB; 16 MiB deixa folga ampla contra
    # ruído de RSS sem mascarar um vazamento por quadro de verdade.
    assert growth_mb < 16, \
        f"memória cresceu {growth_mb:.1f} MiB em 500 quadros"
