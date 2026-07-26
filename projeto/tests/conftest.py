"""Fixtures compartilhadas pelos testes de requisitos.

Os testes rodam em qualquer máquina, sem webcam, OpenCV ou MediaPipe: os
estágios de hardware são substituídos pelas implementações sintéticas do
módulo ``libras.demo`` — os demais estágios exercitados são os reais.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from libras.classifier import KnnClassifier          # noqa: E402
from libras.config import Config                     # noqa: E402
from libras.demo import make_synthetic_dataset       # noqa: E402


@pytest.fixture(scope="session")
def fast_config():
    """Config com janelas temporais curtas, para testes rápidos."""
    return Config(window_size=6, min_votes=4, release_frames=3,
                  word_pause_frames=10, target_fps=0)


@pytest.fixture(scope="session")
def synthetic_dataset():
    """(X, y, prototipos) do alfabeto sintético determinístico."""
    return make_synthetic_dataset()


@pytest.fixture(scope="session")
def trained_classifier(synthetic_dataset):
    X, y, _ = synthetic_dataset
    return KnnClassifier(k=5).fit(X, y)
