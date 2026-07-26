"""RF-02 — Conexão da webcam.

Cenário da Tabela 1 do documento de arquitetura: "Pela porta USB da placa,
testar recepção, processamento e exibição" → "O Raspberry Pi recebe,
processa e exibe os dados da webcam". Validamos o contrato da fonte de
vídeo, o pré-processamento e o caminho recepção → processamento → quadro de
exibição do pipeline, com uma fonte sintética no lugar da webcam física.
"""
import importlib.util

import numpy as np
import pytest

from libras.capture import CameraError, CameraSource, SyntheticSource
from libras.demo import make_demo_components
from libras.pipeline import PipelineState, TranslationPipeline
from libras.preprocess import preprocess, resize_width

CV2_AVAILABLE = importlib.util.find_spec("cv2") is not None


def test_fonte_gera_quadros_bgr_validos():
    source = SyntheticSource(width=640, height=480)
    frames = [source.read() for _ in range(5)]
    for frame in frames:
        assert frame is not None
        assert frame.shape == (480, 640, 3)
        assert frame.dtype == np.uint8
    assert not np.array_equal(frames[0], frames[1]), \
        "quadros devem variar no tempo"


def test_fonte_finita_encerra_com_none():
    source = SyntheticSource(max_frames=3)
    assert all(source.read() is not None for _ in range(3))
    assert source.read() is None


@pytest.mark.skipif(CV2_AVAILABLE,
                    reason="cv2 instalado; o cenário é a ausência do OpenCV")
def test_camera_sem_opencv_falha_com_mensagem_clara():
    with pytest.raises(CameraError, match="OpenCV"):
        CameraSource(0)


@pytest.mark.skipif(not CV2_AVAILABLE, reason="requer OpenCV instalado")
def test_camera_com_indice_invalido_falha_com_mensagem_clara():
    with pytest.raises(CameraError, match="câmera"):
        CameraSource(9999)


def test_preprocessamento_redimensiona_preservando_proporcao():
    frame = SyntheticSource(width=640, height=480).read()
    small = resize_width(frame, 320)
    assert small.shape == (240, 320, 3)


def test_preprocessamento_converte_bgr_para_rgb():
    frame = np.zeros((4, 4, 3), dtype=np.uint8)
    frame[..., 0] = 10    # canal B
    frame[..., 2] = 200   # canal R
    rgb = preprocess(frame, 4)
    assert rgb[0, 0, 0] == 200 and rgb[0, 0, 2] == 10
    assert rgb.flags["C_CONTIGUOUS"]


def test_recepcao_processamento_e_exibicao(fast_config):
    """Caminho completo do cenário de teste do RF-02."""
    source, extractor, classifier = make_demo_components(fast_config)
    state = PipelineState()
    pipeline = TranslationPipeline(source, extractor, classifier,
                                   fast_config, state=state)
    for _ in range(30):
        assert pipeline.step()

    snapshot = state.to_dict()
    assert snapshot["quadros_processados"] == 30              # recepção
    assert snapshot["fps"] > 0                                # processamento
    assert set(snapshot["latencia_ms"]) == {"captura", "preprocessamento",
                                            "landmarks", "classificacao"}
    frame = pipeline.latest_frame()                           # exibição
    assert frame is not None
    assert frame.shape == (fast_config.frame_height, fast_config.frame_width, 3)
