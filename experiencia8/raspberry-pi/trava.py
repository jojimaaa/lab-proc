#!/usr/bin/env python3
"""
Controle ISOLADO do atuador da tranca (o "ferrolho" que abre/fecha).
Experiencia 8 (PCS3732) - item "Implemente isoladamente o controle de cada
componente" -> aqui a TRANCA / LOCK MECH (RF05: acionamento ao validar a senha).

Dois tipos, escolhidos por --tipo:
  servo (PADRAO): servomotor SG90 movimenta o ferrolho.
                  trancada = 0 graus ; destrancada = 90 graus.
                  Backend automatico: pigpio (pulso por DMA, suave) se o daemon
                  estiver no ar; senao RPi.GPIO (PWM por software, com tremor) -
                  mesma hierarquia discutida na Experiencia 7.
  rele  : rele/solenoide acionado por 1 GPIO digital (destrancada = acionado).

Uso:
  python3 trava.py                 # servo: tranca -> destranca -> tranca
  python3 trava.py --pino 18
  python3 trava.py --tipo rele --pino 18
"""

import time
import argparse

FREQ_HZ         = 50            # base do SG90 (periodo 20 ms)
ANG_TRANCADA    = 0
ANG_DESTRANCADA = 90
MIN_US, MAX_US  = 500, 2500     # calibracao de largura de pulso (0..180 graus)


def _ang_para_us(ang):
    ang = max(0.0, min(180.0, ang))
    return MIN_US + (ang / 180.0) * (MAX_US - MIN_US)


class Trava:
    """Atuador da tranca: expoe trancar() / destrancar()."""

    def __init__(self, tipo="servo", pino=18, rele_ativo_alto=True, setup_gpio=True):
        self.tipo, self.pino = tipo, pino
        self.rele_ativo_alto = rele_ativo_alto
        self.backend = None
        self._trancada = True
        if tipo == "servo":
            self._init_servo(setup_gpio)
        elif tipo == "rele":
            self._init_rele(setup_gpio)
        else:
            raise ValueError("tipo deve ser 'servo' ou 'rele'")
        self.trancar()

    # -- servo: pigpio (suave) com fallback RPi.GPIO -------------------------
    def _init_servo(self, setup_gpio):
        try:
            import pigpio
            pi = pigpio.pi()
            if pi.connected:
                self._pi = pi
                self.backend = "pigpio"
                print("[trava] servo via pigpio (DMA) - movimento suave.")
                return
        except ImportError:
            pass
        import RPi.GPIO as GPIO
        self._GPIO = GPIO
        if setup_gpio:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
        GPIO.setup(self.pino, GPIO.OUT)
        self._pwm = GPIO.PWM(self.pino, FREQ_HZ)
        self._pwm.start(0)
        self.backend = "RPi.GPIO"
        print("[trava] servo via RPi.GPIO (PWM por software) - pode tremer.")

    def _init_rele(self, setup_gpio):
        import RPi.GPIO as GPIO
        self._GPIO = GPIO
        if setup_gpio:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
        nivel_repouso = GPIO.LOW if self.rele_ativo_alto else GPIO.HIGH
        GPIO.setup(self.pino, GPIO.OUT, initial=nivel_repouso)
        self.backend = "rele"

    def _servo_para(self, ang):
        us = _ang_para_us(ang)
        if self.backend == "pigpio":
            self._pi.set_servo_pulsewidth(self.pino, us)
        else:
            self._pwm.ChangeDutyCycle(us / 200.0)   # us / 20000us * 100
        time.sleep(0.4)                              # tempo p/ o servo chegar
        if self.backend == "pigpio":
            self._pi.set_servo_pulsewidth(self.pino, 0)   # relaxa (menos tremor)
        else:
            self._pwm.ChangeDutyCycle(0)

    def _rele(self, acionado):
        on = self._GPIO.HIGH if self.rele_ativo_alto else self._GPIO.LOW
        off = self._GPIO.LOW if self.rele_ativo_alto else self._GPIO.HIGH
        self._GPIO.output(self.pino, on if acionado else off)

    # -- API de alto nivel ---------------------------------------------------
    def trancar(self):
        if self.tipo == "servo":
            self._servo_para(ANG_TRANCADA)
        else:
            self._rele(False)
        self._trancada = True

    def destrancar(self):
        if self.tipo == "servo":
            self._servo_para(ANG_DESTRANCADA)
        else:
            self._rele(True)
        self._trancada = False

    def esta_trancada(self):
        return self._trancada

    def close(self):
        try:
            self.trancar()
        finally:
            if self.backend == "pigpio":
                self._pi.set_servo_pulsewidth(self.pino, 0)
                self._pi.stop()
            elif self.backend == "RPi.GPIO":
                self._pwm.stop()
                self._GPIO.cleanup()
            else:
                self._GPIO.cleanup()


def main():
    p = argparse.ArgumentParser(description="Teste isolado do atuador da tranca.")
    p.add_argument("--tipo", choices=["servo", "rele"], default="servo")
    p.add_argument("--pino", type=int, default=18, help="GPIO (BCM) do atuador.")
    args = p.parse_args()

    tr = Trava(tipo=args.tipo, pino=args.pino)
    print(f"==== Teste de Tranca (Exp 8) - tipo '{args.tipo}' GPIO{args.pino} ====")
    try:
        print("   TRANCADA");   tr.trancar();    time.sleep(1.0)
        print("   DESTRANCADA"); tr.destrancar(); time.sleep(1.5)
        print("   TRANCADA");   tr.trancar();    time.sleep(1.0)
        print("\nConcluido.")
    except KeyboardInterrupt:
        print("\nInterrompido.")
    finally:
        tr.close()


if __name__ == "__main__":
    main()
