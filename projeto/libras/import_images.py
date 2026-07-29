"""Gera o dataset a partir de um banco de imagens pronto — sem saber LIBRAS.

Alternativa à coleta com webcam (``python -m libras.collect``): baixe um
dataset público de imagens do alfabeto em LIBRAS (links no README), organize
uma subpasta por letra e rode este importador. Ele extrai os landmarks de
cada imagem com o MediaPipe e grava as características no dataset CSV usado
pelo classificador.

Estrutura esperada da pasta de entrada:
    imagens/
    ├── A/  *.jpg | *.jpeg | *.png
    ├── B/  ...
    └── ...

Uso:
    python -m libras.import_images caminho/para/imagens [--dataset data/dataset.csv]
                                   [--limite 200]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from .classifier import append_samples
from .config import DEFAULT_DATASET, Config
from .features import normalize_landmarks
from .landmarks import MediaPipeExtractor

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}

# Desvio do jitter sintético, aplicado no espaço JÁ normalizado (mão com
# raio 1): da mesma ordem do ruído de detecção em webcam ao vivo. Jitter nos
# landmarks brutos passaria pelos ramos discretos da normalização (rotação e
# espelho) e ocasionalmente produziria poses corrompidas.
AUGMENT_NOISE = 0.03


def main(argv=None) -> int:
    import cv2  # a importação de imagens exige OpenCV instalado

    parser = argparse.ArgumentParser(
        prog="python -m libras.import_images",
        description="Converte um banco de imagens do alfabeto em LIBRAS "
                    "no dataset de landmarks do classificador")
    parser.add_argument("pasta", help="pasta com uma subpasta por letra")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET),
                        help="CSV de saída (acrescenta ao existente)")
    parser.add_argument("--limite", type=int, default=0,
                        help="máximo de imagens por letra (0 = todas)")
    parser.add_argument("--augment", type=int, default=3,
                        help="variações sintéticas por imagem (jitter nos "
                             "landmarks, simula webcam ao vivo; 0 desliga)")
    args = parser.parse_args(argv)
    rng = np.random.default_rng(42)

    root = Path(args.pasta)
    if not root.is_dir():
        print(f"Pasta não encontrada: {root}", file=sys.stderr)
        return 2

    letter_dirs = sorted(d for d in root.iterdir()
                         if d.is_dir() and len(d.name) == 1
                         and d.name.upper().isalpha())
    if not letter_dirs:
        print(f"Nenhuma subpasta de letra (A–Z) em {root}.\n"
              "Estrutura esperada: uma subpasta por letra, ex.: imagens/A/*.jpg",
              file=sys.stderr)
        return 2

    # Mesmo model_complexity da execução (ver Config): o dataset precisa ser
    # gerado com o modelo que vai consultá-lo.
    extractor = MediaPipeExtractor(
        static=True, model_complexity=Config.model_complexity)
    totals: "dict[str, int]" = {}
    skipped = 0
    try:
        for letter_dir in letter_dirs:
            letter = letter_dir.name.upper()
            features = []
            images_used = 0
            for image_path in sorted(letter_dir.iterdir()):
                if image_path.suffix.lower() not in IMAGE_EXTENSIONS:
                    continue
                if args.limite and images_used >= args.limite:
                    break
                image = cv2.imread(str(image_path))
                if image is None:
                    skipped += 1
                    continue
                rgb = image[..., ::-1].copy()  # BGR -> RGB contíguo
                detection = extractor.extract(rgb)
                if detection is None:
                    skipped += 1  # nenhuma mão detectada na imagem
                    continue
                images_used += 1
                clean = normalize_landmarks(detection.landmarks)
                features.append(clean)
                # Uma foto congela UMA pose exata; as variações com jitter
                # preenchem a vizinhança onde os quadros da webcam vão cair.
                for _ in range(args.augment):
                    features.append(clean + rng.normal(
                        0.0, AUGMENT_NOISE, clean.shape).astype(np.float32))
            if features:
                append_samples(args.dataset, letter, features)
                totals[letter] = len(features)
            print(f"  {letter}: {len(features)} amostras")
    finally:
        extractor.close()

    total = sum(totals.values())
    print(f"\nImportação concluída: {total} amostras de {len(totals)} letras "
          f"gravadas em {args.dataset}")
    if skipped:
        print(f"({skipped} imagens ignoradas: ilegíveis ou sem mão detectada)")
    if total:
        print("Pronto para rodar:  python -m libras.main")
    return 0 if total else 1


if __name__ == "__main__":
    raise SystemExit(main())
