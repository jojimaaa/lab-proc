#!/usr/bin/env python3
"""
Controle ISOLADO do buzzer.
Experiencia 7 (PCS3732) - item "Implemente isoladamente o controle do buzzer".

Dois tipos de buzzer:
  - ATIVO  (padrao): tem oscilador interno; basta nivel logico ALTO para apitar.
                     Controlado por sinal DIGITAL on/off (como no diagrama do
                     enunciado: "Sinal Digital").
  - PASSIVO (--passivo): precisa de uma onda quadrada na frequencia da nota;
                     geramos o tom com PWM (GPIO.PWM na frequencia desejada).

Fiacao: um terminal no GPIO, outro no GND.
Uso:
  python3 buzzer.py                 # buzzer ATIVO: padrao de bipes
  python3 buzzer.py --pino 12
  python3 buzzer.py --passivo       # buzzer PASSIVO: toca uma escala (tons)
"""

import time
import argparse

try:
    import RPi.GPIO as GPIO
except (ImportError, RuntimeError):
    raise SystemExit("Rode em um Raspberry Pi com RPi.GPIO instalado.")

PIN_BUZZER_PADRAO = 12

# Notas (Hz) para o modo passivo - uma oitava de Do maior.
ESCALA = [("Do", 262), ("Re", 294), ("Mi", 330), ("Fa", 349),
          ("Sol", 392), ("La", 440), ("Si", 494), ("Do+", 523)]


def bipe(pino, dur_on=0.1, dur_off=0.1, n=1):
    """Buzzer ATIVO: liga/desliga por nivel digital."""
    for _ in range(n):
        GPIO.output(pino, GPIO.HIGH)
        time.sleep(dur_on)
        GPIO.output(pino, GPIO.LOW)
        time.sleep(dur_off)


def demo_ativo(pino):
    print("\n[buzzer ATIVO] sinal digital on/off")
    print("    1 bipe curto"); bipe(pino, 0.12, 0.3, n=1)
    print("    2 bipes");      bipe(pino, 0.10, 0.10, n=2); time.sleep(0.3)
    print("    bipe longo");   bipe(pino, 0.6, 0.2, n=1)


def demo_passivo(pino):
    """Buzzer PASSIVO: gera o tom com PWM (onda quadrada na freq da nota)."""
    print("\n[buzzer PASSIVO] tons via PWM (escala de Do maior)")
    tom = GPIO.PWM(pino, ESCALA[0][1])
    tom.start(50)                    # 50% de duty = onda quadrada
    try:
        for nome, freq in ESCALA:
            print(f"    {nome:>4} = {freq} Hz")
            tom.ChangeFrequency(freq)
            time.sleep(0.4)
    finally:
        tom.stop()


def main():
    p = argparse.ArgumentParser(description="Controle isolado do buzzer.")
    p.add_argument("--pino", type=int, default=PIN_BUZZER_PADRAO, help="GPIO (BCM) do buzzer.")
    p.add_argument("--passivo", action="store_true",
                   help="Trata como buzzer passivo e toca tons via PWM.")
    args = p.parse_args()

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(args.pino, GPIO.OUT, initial=GPIO.LOW)

    print(f"==== Teste de Buzzer (Exp 7) - GPIO{args.pino} ====")
    try:
        if args.passivo:
            demo_passivo(args.pino)
        else:
            demo_ativo(args.pino)
        print("\nConcluido.")
    except KeyboardInterrupt:
        print("\nInterrompido.")
    finally:
        GPIO.output(args.pino, GPIO.LOW)
        GPIO.cleanup()


if __name__ == "__main__":
    main()
