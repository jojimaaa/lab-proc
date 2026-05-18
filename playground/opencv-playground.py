import cv2

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

model_path = 'models/gesture_recognizer.task'

BaseOptions = python.BaseOptions
GestureRecognizerOptions = vision.GestureRecognizerOptions
GestureRecognizer = vision.GestureRecognizer
GestureRecognizerResult = vision.GestureRecognizerResult
RunningMode = vision.RunningMode

def print_result(result: vision.GestureRecognizerResult, output_image: mp.Image, timestamp_ms: int):
  if result.gestures:
    for hand_gestures in result.gestures:
      print('Gesture: {}'.format(hand_gestures[0].category_name))

options = GestureRecognizerOptions(
  base_options=BaseOptions(model_asset_path=model_path),
  running_mode=RunningMode.LIVE_STREAM,
  result_callback=print_result
)


with GestureRecognizer.create_from_options(options) as recognizer:
  vc = cv2.VideoCapture(0)
  fps = vc.get(cv2.CAP_PROP_FPS) or 30
  frame_index = 0

  while True:
    key = cv2.waitKey(10)
    if (key == 27): # ESC
      break

    hasFrame, frame = vc.read()

    if not hasFrame:
        break

    timestamp_ms = int((frame_index / fps) * 1000)
    frame_index += 1

    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)

    recognizer.recognize_async(mp_image, timestamp_ms)

    cv2.imshow("window", frame)
