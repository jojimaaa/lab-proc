"""
keypad.py - Leitor de teclado matricial 4x4 via GPIO (Raspberry Pi).

Varredura por linha/coluna: as linhas sao saidas, as colunas entradas com
pull-up interno. Aciona-se uma linha por vez em nivel BAIXO e leem-se as
colunas -- a tecla pressionada "aterra" sua coluna. Debounce por software.

Pinos (BCM) -- ajuste se ligar em outros GPIOs:
    Linhas  (saida)  : 5, 6, 13, 19   (pinos fisicos 29, 31, 33, 35)
    Colunas (entrada): 12, 16, 20, 21 (pinos fisicos 32, 36, 38, 40)
"""
import time

try:
    import RPi.GPIO as GPIO
except ImportError:
    raise SystemExit(
        "RPi.GPIO nao encontrado.\n"
        "  Raspberry Pi OS (Bullseye): sudo apt install python3-rpi.gpio\n"
        "  Raspberry Pi OS (Bookworm): pip install rpi-lgpio"
    )

ROWS = [5, 6, 13, 19]
COLS = [12, 16, 20, 21]
KEYS = [
    ['1', '2', '3', 'A'],
    ['4', '5', '6', 'B'],
    ['7', '8', '9', 'C'],
    ['*', '0', '#', 'D'],
]


class Keypad:
    def __init__(self, rows=ROWS, cols=COLS, keys=KEYS):
        self.rows, self.cols, self.keys = rows, cols, keys
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        for r in self.rows:
            GPIO.setup(r, GPIO.OUT, initial=GPIO.HIGH)
        for c in self.cols:
            GPIO.setup(c, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def _scan(self):
        """Retorna a tecla pressionada agora, ou None."""
        for ri, r in enumerate(self.rows):
            GPIO.output(r, GPIO.LOW)
            for ci, c in enumerate(self.cols):
                if GPIO.input(c) == GPIO.LOW:
                    GPIO.output(r, GPIO.HIGH)
                    return self.keys[ri][ci]
            GPIO.output(r, GPIO.HIGH)
        return None

    def get_key(self, debounce=0.03):
        """Bloqueia ate uma tecla ser pressionada; espera soltar (debounce)."""
        while True:
            k = self._scan()
            if k is not None:
                time.sleep(debounce)
                while self._scan() is not None:   # espera liberar
                    time.sleep(0.01)
                return k
            time.sleep(0.005)

    def cleanup(self):
        GPIO.cleanup()
