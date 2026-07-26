"""Normalização geométrica dos landmarks — a entrada do classificador.

Trabalhar sobre 21 coordenadas normalizadas (em vez da imagem completa)
reduz a dimensionalidade e torna o reconhecimento robusto a variações de
fundo, posição e distância da câmera (Seção 7.2 do documento de
arquitetura).
"""
from __future__ import annotations

import numpy as np

FEATURE_SIZE = 42  # 21 pontos × (x, y)


def normalize_landmarks(landmarks) -> np.ndarray:
    """Translada o punho (ponto 0) para a origem e divide pela maior
    distância ao punho.

    O vetor resultante (42 floats) é invariante à posição da mão no quadro
    e à distância da câmera — duas variações que não alteram o sinal.
    """
    pts = np.asarray(landmarks, dtype=np.float32)[:, :2].copy()
    pts -= pts[0]
    scale = float(np.max(np.linalg.norm(pts, axis=1)))
    if scale > 1e-9:
        pts /= scale
    return pts.reshape(-1)
