"""RF-03 — Reconhecimento de sinais por modelo de visão computacional.

Cenário da Tabela 1 do documento de arquitetura: "Executar o alfabeto em
LIBRAS diante da webcam e verificar o resultado" → "Alfabeto inteiro
reconhecido corretamente pelo modelo". O alfabeto sintético percorre o
classificador e a lógica temporal de confirmação (Figuras 2 e 3).
"""
import numpy as np
import pytest

from libras.classifier import KnnClassifier, NotFittedError, Prediction
from libras.demo import ALPHABET, spell_sequence
from libras.features import normalize_landmarks
from libras.temporal import LetterConfirmer


def test_alfabeto_inteiro_reconhecido(trained_classifier, synthetic_dataset):
    _, _, prototypes = synthetic_dataset
    rng = np.random.default_rng(123)
    recognized = []
    for letter in ALPHABET:
        sample = prototypes[letter] + rng.normal(0, 0.01, (21, 2)).astype(np.float32)
        prediction = trained_classifier.predict(normalize_landmarks(sample))
        recognized.append(prediction.label)
    assert recognized == list(ALPHABET)


def test_invariancia_a_posicao_e_distancia_da_camera(trained_classifier,
                                                     synthetic_dataset):
    """O mesmo gesto, com a mão menor e deslocada no quadro, é a mesma letra."""
    _, _, prototypes = synthetic_dataset
    transformed = prototypes["A"] * 0.4 + np.float32([0.3, -0.2])
    prediction = trained_classifier.predict(normalize_landmarks(transformed))
    assert prediction.label == "A"


def test_confianca_alta_para_amostra_limpa(trained_classifier,
                                           synthetic_dataset):
    _, _, prototypes = synthetic_dataset
    prediction = trained_classifier.predict(
        normalize_landmarks(prototypes["M"]))
    assert prediction.label == "M"
    assert 0.9 <= prediction.confidence <= 1.0


def test_classificador_sem_dataset_gera_erro_claro():
    with pytest.raises(NotFittedError):
        KnnClassifier().predict(np.zeros(42, dtype=np.float32))


def test_letra_so_confirma_apos_estabilidade():
    confirmer = LetterConfirmer(min_confidence=0.7, window_size=6,
                                min_votes=4, release_frames=3)
    prediction = Prediction("A", 0.95)
    assert [confirmer.update(prediction) for _ in range(3)] == [None] * 3
    assert confirmer.update(prediction) == "A"
    assert confirmer.update(prediction) is None  # mão mantida: não repete


def test_predicao_com_baixa_confianca_e_descartada():
    confirmer = LetterConfirmer(min_confidence=0.7, window_size=6,
                                min_votes=4, release_frames=3)
    for _ in range(20):
        assert confirmer.update(Prediction("A", 0.5)) is None


def test_oscilacao_entre_classes_nao_confirma():
    confirmer = LetterConfirmer(min_confidence=0.7, window_size=6,
                                min_votes=4, release_frames=3)
    for i in range(30):
        prediction = Prediction("A" if i % 2 == 0 else "B", 0.95)
        assert confirmer.update(prediction) is None


def test_alfabeto_executado_em_sequencia_de_video(trained_classifier,
                                                  synthetic_dataset):
    """Reproduz o cenário da Tabela 1 quadro a quadro, com gestos ruidosos."""
    _, _, prototypes = synthetic_dataset
    sequence = spell_sequence(" ".join(ALPHABET), prototypes,
                              hold_frames=8, gap_frames=5,
                              word_pause_frames=6)
    confirmer = LetterConfirmer(min_confidence=0.7, window_size=6,
                                min_votes=4, release_frames=3)
    confirmed = []
    for detection in sequence:
        prediction = (trained_classifier.predict_landmarks(detection.landmarks)
                      if detection else None)
        letter = confirmer.update(prediction)
        if letter:
            confirmed.append(letter)
    assert confirmed == list(ALPHABET)
