#!/usr/bin/env python3
"""
Controle ISOLADO de LED por PWM + teste de diversas frequencias.
Experiencia 7 (PCS3732) - item "Implemente o controle de um LED usando PWM e
teste diversas frequencias".

O que este programa demonstra:
  1) Varredura de DUTY CYCLE (0% -> 100% -> 0%) numa frequencia fixa: mostra que
     o brilho medio do LED e proporcional ao duty cycle.
  2) Varredura de FREQUENCIA: mantem o duty em 50% e percorre varias frequencias.
     Em frequencias baixas (1-20 Hz) enxerga-se a CINTILACAO; acima de ~60-80 Hz
     a persistencia da visao funde os pulsos e o LED parece aceso continuo.

Fiacao: LED em serie com resistor de 330 ohm entre o GPIO e o GND.
Uso:
  python3 led_pwm.py                 # roda as duas demonstracoes
  python3 led_pwm.py --pino 17
  python3 led_pwm.py --freqs 1 2 5 10 30 60 120 1000
"""

import time
import argparse

try:
    import RPi.GPIO as GPIO
except (ImportError, RuntimeError):
    raise SystemExit("Rode em um Raspberry Pi com RPi.GPIO instalado.")

PIN_LED_PADRAO = 17
FREQS_PADRAO   = [1, 2, 5, 10, 20, 60, 120, 1000]   # Hz


def varredura_duty(led, ciclos=2, passos=50, freq=1000):
    """Sobe e desce o duty cycle para mostrar o controle de brilho."""
    print(f"\n[1] Varredura de DUTY CYCLE @ {freq} Hz (brilho 0%->100%->0%)")
    led.ChangeFrequency(freq)
    for _ in range(ciclos):
        for d in range(0, passos + 1):
            led.ChangeDutyCycle(100.0 * d / passos)
            time.sleep(0.02)
        for d in range(passos, -1, -1):
            led.ChangeDutyCycle(100.0 * d / passos)
            time.sleep(0.02)
    led.ChangeDutyCycle(0)


def varredura_frequencia(led, freqs, segundos=2.5, duty=50.0):
    """Fixa o duty e percorre varias frequencias, segurando cada uma para que
    a cintilacao (freq baixa) x fusao (freq alta) possa ser observada."""
    print(f"\n[2] Varredura de FREQUENCIA (duty fixo em {duty:.0f}%)")
    led.ChangeDutyCycle(duty)
    for f in freqs:
        obs = "cintila visivelmente" if f <= 24 else \
              ("no limiar da fusao" if f < 60 else "parece aceso continuo")
        print(f"    f = {f:>5} Hz  ->  {obs}")
        led.ChangeFrequency(f)
        time.sleep(segundos)
    led.ChangeDutyCycle(0)


def main():
    p = argparse.ArgumentParser(description="LED por PWM: teste de duty e frequencias.")
    p.add_argument("--pino", type=int, default=PIN_LED_PADRAO, help="GPIO (BCM) do LED.")
    p.add_argument("--freqs", type=int, nargs="+", default=FREQS_PADRAO,
                   help="Lista de frequencias (Hz) a testar.")
    args = p.parse_args()

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(args.pino, GPIO.OUT)

    led = GPIO.PWM(args.pino, FREQS_PADRAO[-1])   # frequencia inicial
    led.start(0)
    print(f"==== Teste de LED por PWM (Exp 7) - GPIO{args.pino} ====")
    try:
        varredura_duty(led)
        varredura_frequencia(led, args.freqs)
        print("\nConcluido.")
    except KeyboardInterrupt:
        print("\nInterrompido.")
    finally:
        led.stop()
        GPIO.cleanup()


if __name__ == "__main__":
    main()
