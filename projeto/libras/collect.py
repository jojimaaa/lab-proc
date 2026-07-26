"""Coleta de amostras reais para o classificador (requer webcam + MediaPipe).

Uso:
    python -m libras.collect [--camera 0] [--dataset data/dataset.csv] [--burst 20]

Na janela de vídeo:
  - faça o gesto da letra e pressione a tecla correspondente (A–Z) para
    gravar uma rajada de amostras;
  - pressione ESC para encerrar.

Recomenda-se ao menos ~20 amostras por letra, variando levemente o ângulo e
a distância da mão.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from .capture import CameraSource
from .classifier import append_samples, load_dataset
from .config import DEFAULT_DATASET, Config
from .features import normalize_landmarks
from .landmarks import MediaPipeExtractor
from .preprocess import preprocess

# Conexões do esqueleto da mão (índices dos 21 landmarks do MediaPipe).
HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),          # polegar
    (0, 5), (5, 6), (6, 7), (7, 8),          # indicador
    (5, 9), (9, 10), (10, 11), (11, 12),     # médio
    (9, 13), (13, 14), (14, 15), (15, 16),   # anelar
    (13, 17), (17, 18), (18, 19), (19, 20),  # mínimo
    (0, 17),
)


def main(argv=None) -> int:
    import cv2  # a coleta só faz sentido com OpenCV instalado

    parser = argparse.ArgumentParser(
        prog="python -m libras.collect",
        description="Coleta de amostras de gestos para o classificador")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--burst", type=int, default=20,
                        help="amostras gravadas por tecla pressionada")
    args = parser.parse_args(argv)

    config = Config(camera_index=args.camera)
    dataset_path = Path(args.dataset)
    counts: "Counter[str]" = Counter()
    if dataset_path.exists():
        _, labels = load_dataset(dataset_path)
        counts.update(labels)
        print(f"Dataset existente: {sum(counts.values())} amostras, "
              f"{len(counts)} letras.")

    source = CameraSource(config.camera_index, config.frame_width,
                          config.frame_height)
    extractor = MediaPipeExtractor()
    burst_left = 0
    burst_label: "str | None" = None

    print("Coleta de amostras — pressione a letra (A–Z) para gravar; ESC sai.")
    try:
        while True:
            frame = source.read()
            if frame is None:
                break
            rgb = preprocess(frame, config.process_width)
            detection = extractor.extract(rgb)

            h, w = frame.shape[:2]
            if detection is not None:
                pts = [(int(x * w), int(y * h))
                       for x, y in detection.landmarks[:, :2]]
                for a, b in HAND_CONNECTIONS:
                    cv2.line(frame, pts[a], pts[b], (0, 200, 255), 1)
                for p in pts:
                    cv2.circle(frame, p, 3, (0, 255, 0), -1)
                if burst_left > 0 and burst_label:
                    append_samples(dataset_path, burst_label,
                                   [normalize_landmarks(detection.landmarks)])
                    counts[burst_label] += 1
                    burst_left -= 1

            status = (f"gravando '{burst_label}': faltam {burst_left}"
                      if burst_left else "aguardando tecla A-Z")
            cv2.putText(frame, status, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 128), 2)
            cv2.putText(frame,
                        f"amostras: {sum(counts.values())} | letras: {len(counts)}",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                        (255, 255, 255), 2)
            cv2.imshow("Coleta LIBRAS", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                break
            if burst_left == 0 and (65 <= key <= 90 or 97 <= key <= 122):
                burst_label = chr(key).upper()
                burst_left = args.burst
                print(f"Gravando {args.burst} amostras da letra {burst_label}…")
    finally:
        source.release()
        extractor.close()
        cv2.destroyAllWindows()

    print("Resumo da coleta:", dict(sorted(counts.items())))
    print(f"Dataset salvo em {dataset_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
