#!/usr/bin/env python3
"""
Controle ISOLADO de servomotor SG90 por PWM.
Experiencia 7 (PCS3732) - item "Implemente isoladamente o controle de
servomotor usando PWM".

Base do SG90: sinal PWM de 50 Hz (periodo de 20 ms). A largura do pulso define
o angulo:
    1.0 ms  ->  5.0 % de duty  ->    0 graus
    1.5 ms  ->  7.5 % de duty  ->   90 graus
    2.0 ms  -> 10.0 % de duty  ->  180 graus
Relacao linear usada:  duty(%) = 5.0 + (angulo/180) * 5.0

Fiacao: sinal no GPIO; alimente o servo com +5V e GND (de preferencia por fonte
externa, com o GND comum ao do Raspberry Pi).
Uso:
  python3 servo.py                 # posicoes fixas + varredura continua
  python3 servo.py --pino 18
  python3 servo.py --angulo 90     # vai direto a um angulo e sai
"""

import time
import argparse

try:
    import RPi.GPIO as GPIO
except (ImportError, RuntimeError):
    raise SystemExit("Rode em um Raspberry Pi com RPi.GPIO instalado.")

PIN_SERVO_PADRAO = 18
FREQ_HZ = 50           # 20 ms de periodo (base do SG90)


def angulo_para_duty(angulo):
    """Mapeia 0..180 graus para o duty cycle (5%..10%) a 50 Hz."""
    angulo = max(0.0, min(180.0, angulo))
    return 5.0 + (angulo / 180.0) * 5.0


def ir_para(servo, angulo, espera=0.5):
    duty = angulo_para_duty(angulo)
    print(f"    angulo = {angulo:>5.1f} graus  ->  duty = {duty:.2f}%")
    servo.ChangeDutyCycle(duty)
    time.sleep(espera)
    servo.ChangeDutyCycle(0)      # evita "tremor" do servo mantendo o pulso


def demo(servo):
    print("\n[1] Posicoes fixas: 0 -> 90 -> 180 -> 90 -> 0")
    for a in (0, 90, 180, 90, 0):
        ir_para(servo, a, espera=0.6)

    print("\n[2] Varredura continua 0 -> 180 -> 0")
    for a in list(range(0, 181, 5)) + list(range(180, -1, -5)):
        servo.ChangeDutyCycle(angulo_para_duty(a))
        time.sleep(0.03)
    servo.ChangeDutyCycle(0)


def main():
    p = argparse.ArgumentParser(description="Servo SG90 por PWM (50 Hz).")
    p.add_argument("--pino", type=int, default=PIN_SERVO_PADRAO, help="GPIO (BCM) do servo.")
    p.add_argument("--angulo", type=float, default=None,
                   help="Se informado, vai a esse angulo (0..180) e encerra.")
    args = p.parse_args()

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(args.pino, GPIO.OUT)

    servo = GPIO.PWM(args.pino, FREQ_HZ)
    servo.start(0)
    print(f"==== Teste de Servo SG90 por PWM (Exp 7) - GPIO{args.pino} @ {FREQ_HZ} Hz ====")
    try:
        if args.angulo is not None:
            ir_para(servo, args.angulo, espera=0.8)
        else:
            demo(servo)
        print("\nConcluido.")
    except KeyboardInterrupt:
        print("\nInterrompido.")
    finally:
        servo.stop()
        GPIO.cleanup()


if __name__ == "__main__":
    main()
