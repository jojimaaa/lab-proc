#!/usr/bin/env python3
"""
Controle ISOLADO de servomotor SG90 por PWM.
Experiencia 7 (PCS3732) - item "Implemente isoladamente o controle de
servomotor usando PWM".

DOIS BACKENDS DE PWM (o programa escolhe sozinho):
  - pigpio  (PREFERIDO): pulso temporizado por DMA -> movimento SUAVE, sem
            tremor. Precisa do daemon:  sudo apt install pigpio python3-pigpio
                                        sudo systemctl enable --now pigpiod
  - RPi.GPIO (fallback): PWM por software -> funciona, mas o servo TREME (jitter
            do escalonador do Linux). So use se nao puder instalar o pigpio.

CALIBRACAO (o motivo de "so ir ate 90 graus"):
  A base do SG90 e 50 Hz (periodo 20 ms). O angulo vem da LARGURA DO PULSO:
      pulso ~0.5 ms  ->    0 graus
      pulso ~1.5 ms  ->   90 graus
      pulso ~2.5 ms  ->  180 graus
  A tabela ideal do enunciado (1.0-2.0 ms) costuma varrer so ~90 graus em SG90
  reais. Por isso o padrao aqui e 500-2500 us; ajuste com --min-us/--max-us ate
  o SEU servo bater 0 e 180 sem forcar o batente (se rosnar na ponta, reduza).

Fiacao: sinal no GPIO; alimente o servo com +5V e GND (de preferencia por fonte
externa, com o GND comum ao do Raspberry Pi).
Uso:
  python3 servo.py                 # posicoes fixas + varredura continua
  python3 servo.py --pino 18
  python3 servo.py --angulo 90     # vai direto a um angulo e sai
  python3 servo.py --min-us 600 --max-us 2400   # calibracao fina
"""

import time
import argparse

PIN_SERVO_PADRAO = 18
FREQ_HZ   = 50          # 20 ms de periodo (base do SG90)
MIN_US    = 500         # largura de pulso para 0 graus   (calibravel)
MAX_US    = 2500        # largura de pulso para 180 graus (calibravel)
CLAMP_MIN = 400         # limites de seguranca (nunca mande alem disso)
CLAMP_MAX = 2600


def angulo_para_us(angulo, min_us, max_us):
    """Mapeia 0..180 graus para a largura de pulso (us), com trava de seguranca."""
    angulo = max(0.0, min(180.0, angulo))
    us = min_us + (angulo / 180.0) * (max_us - min_us)
    return max(CLAMP_MIN, min(CLAMP_MAX, us))


# ---------------------------------------------------------------------------
# Driver do servo: abstrai pigpio (suave) x RPi.GPIO (fallback jittery)
# ---------------------------------------------------------------------------
class ServoDriver:
    def __init__(self, pino, min_us, max_us):
        self.pino, self.min_us, self.max_us = pino, min_us, max_us
        self.backend = None
        self._init_pigpio() or self._init_rpigpio()

    def _init_pigpio(self):
        try:
            import pigpio
        except ImportError:
            return False
        pi = pigpio.pi()                      # conecta ao daemon pigpiod
        if not pi.connected:
            print("[aviso] pigpio instalado, mas o daemon nao esta no ar.")
            print("        rode:  sudo systemctl enable --now pigpiod")
            return False
        self._pi = pi
        self.backend = "pigpio"
        print("[backend] pigpio (DMA) - movimento suave.")
        return True

    def _init_rpigpio(self):
        import RPi.GPIO as GPIO
        self._GPIO = GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.pino, GPIO.OUT)
        self._pwm = GPIO.PWM(self.pino, FREQ_HZ)
        self._pwm.start(0)
        self.backend = "RPi.GPIO"
        print("[backend] RPi.GPIO (PWM por software) - vai tremer um pouco.")
        print("        para movimento suave: sudo apt install pigpio python3-pigpio")
        print("                              sudo systemctl enable --now pigpiod")
        return True

    def set_us(self, us):
        if self.backend == "pigpio":
            self._pi.set_servo_pulsewidth(self.pino, us)
        else:
            self._pwm.ChangeDutyCycle(us / 200.0)   # us / 20000us * 100

    def set_angulo(self, angulo):
        self.set_us(angulo_para_us(angulo, self.min_us, self.max_us))

    def off(self):
        """Para de enviar pulsos: o servo relaxa e para de tremer parado."""
        if self.backend == "pigpio":
            self._pi.set_servo_pulsewidth(self.pino, 0)
        else:
            self._pwm.ChangeDutyCycle(0)

    def close(self):
        self.off()
        if self.backend == "pigpio":
            self._pi.stop()
        else:
            self._pwm.stop()
            self._GPIO.cleanup()


def ir_para(servo, angulo, espera=0.6):
    us = angulo_para_us(angulo, servo.min_us, servo.max_us)
    print(f"    angulo = {angulo:>5.1f} graus  ->  pulso = {us:.0f} us")
    servo.set_us(us)
    time.sleep(espera)
    servo.off()                 # relaxa entre posicoes -> menos tremor parado


def demo(servo):
    print("\n[1] Posicoes fixas: 0 -> 90 -> 180 -> 90 -> 0")
    for a in (0, 90, 180, 90, 0):
        ir_para(servo, a, espera=0.7)

    print("\n[2] Varredura continua 0 -> 180 -> 0")
    for a in list(range(0, 181, 3)) + list(range(180, -1, -3)):
        servo.set_angulo(a)
        time.sleep(0.03)
    servo.off()


def main():
    p = argparse.ArgumentParser(description="Servo SG90 por PWM (50 Hz).")
    p.add_argument("--pino", type=int, default=PIN_SERVO_PADRAO, help="GPIO (BCM) do servo.")
    p.add_argument("--angulo", type=float, default=None,
                   help="Se informado, vai a esse angulo (0..180) e encerra.")
    p.add_argument("--min-us", type=int, default=MIN_US, help="Pulso (us) para 0 graus.")
    p.add_argument("--max-us", type=int, default=MAX_US, help="Pulso (us) para 180 graus.")
    args = p.parse_args()

    servo = ServoDriver(args.pino, args.min_us, args.max_us)
    print(f"==== Teste de Servo SG90 (Exp 7) - GPIO{args.pino} @ {FREQ_HZ} Hz ====")
    print(f"     calibracao: {args.min_us} us (0 graus) .. {args.max_us} us (180 graus)")
    try:
        if args.angulo is not None:
            ir_para(servo, args.angulo, espera=0.9)
        else:
            demo(servo)
        print("\nConcluido.")
    except KeyboardInterrupt:
        print("\nInterrompido.")
    finally:
        servo.close()


if __name__ == "__main__":
    main()
