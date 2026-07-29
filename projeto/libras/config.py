"""Configurações centrais do tradutor embarcado de LIBRAS.

Os campos estão agrupados pelos blocos do diagrama de blocos (Figura 1 do
documento de arquitetura). Os valores padrão foram pensados para uma
Raspberry Pi 4 com webcam USB a ~25–30 fps.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = PROJECT_ROOT / "data" / "dataset.csv"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
# Modelo da API Tasks do MediaPipe (baixado por: python -m libras.get_model)
MODEL_PATH = PROJECT_ROOT / "data" / "hand_landmarker.task"


@dataclass
class Config:
    # Bloco 1 — captura de vídeo
    camera_index: int = 0
    frame_width: int = 640
    frame_height: int = 480
    target_fps: float = 30.0

    # Bloco 2 — pré-processamento
    process_width: int = 320

    # Bloco 4 — classificador
    knn_k: int = 5

    # Bloco 5 — lógica temporal (votação em janela e montagem de palavras)
    min_confidence: float = 0.65   # limiar de confiança da predição
    window_size: int = 12          # tamanho da janela deslizante de votação
    min_votes: int = 8             # votos mínimos para confirmar uma letra
    release_frames: int = 6        # quadros sem mão p/ liberar letra repetida
    word_pause_frames: int = 30    # quadros sem mão que fecham a palavra

    # Bloco 6 — servidor de aplicação
    host: str = "0.0.0.0"
    port: int = 8001

    # Módulo transversal — monitoramento de desempenho
    monitor_interval: float = 1.0  # s entre amostras de CPU/RAM/temp
    cpi_interval: float = 5.0      # s entre medições de CPI via perf
