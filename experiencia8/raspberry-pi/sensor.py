#!/usr/bin/env python3
"""
Controle ISOLADO do sensor de estado da tranca (Trancada / Aberta).
Experiencia 8 (PCS3732) - item "Implemente isoladamente o controle de cada
componente" -> aqui o SENSOR (RF03: verificar a integridade fisica da tranca).

Sensor Ultrassonico HC-SR04 (TRIG + ECHO). Mede a distancia ate a porta;
abaixo de um limiar considera "trancada/fechada".
ATENCAO: o ECHO do HC-SR04 e de 5V; use um divisor resistivo para nao
aplicar 5V num GPIO de 3,3V do Pi (ver README).

Uso:
  python3 sensor.py                        # HC-SR04 (TRIG=14, ECHO=15)
  python3 sensor.py --trig 14 --echo 15 --limiar-cm 8.0
"""

import time
import argparse

try:
    import RPi.GPIO as GPIO
except (ImportError, RuntimeError):
    raise SystemExit("Rode em um Raspberry Pi com RPi.GPIO instalado.")

PIN_TRIG_PADRAO   = 14          # HC-SR04 trigger
PIN_ECHO_PADRAO   = 15          # HC-SR04 echo (via divisor de tensao!)
LIMIAR_CM_PADRAO  = 8.0         # abaixo disso: porta fechada (trancada)
VEL_SOM_CM_S      = 34300.0     # velocidade do som ~343 m/s
DEBOUNCE_N_PADRAO = 3           # leituras iguais e consecutivas p/ confirmar transicao


class SensorTranca:
    """Abstrai o sensor de estado: expoe esta_trancada() -> bool.

    O HC-SR04 pode oscilar entre leituras (eco perdido, reflexo em angulo,
    porta parada bem no limiar) e trocar de estado rapido demais. Por isso
    esta_trancada() so confirma a transicao apos `debounce_n` leituras
    consecutivas concordando com o novo estado (debounce por contagem,
    equivalente ao usado no teclado - RNF04).
    """

    def __init__(self, trig=PIN_TRIG_PADRAO, echo=PIN_ECHO_PADRAO,
                 limiar_cm=LIMIAR_CM_PADRAO, setup_gpio=True,
                 debounce_n=DEBOUNCE_N_PADRAO):
        self.trig, self.echo, self.limiar_cm = trig, echo, limiar_cm
        self.debounce_n = max(1, debounce_n)
        self._estado_confirmado = None   # ultimo estado estavel reportado
        self._candidato = None           # estado que esta tentando confirmar
        self._contagem = 0
        if setup_gpio:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
        GPIO.setup(self.trig, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.echo, GPIO.IN)
        time.sleep(0.05)     # estabiliza o sensor

    # -- leitura de distancia do HC-SR04 (cm); None se estourar o timeout ----
    def _distancia_cm(self, timeout=0.03):
        GPIO.output(self.trig, GPIO.HIGH)
        time.sleep(0.00001)              # pulso de 10 us
        GPIO.output(self.trig, GPIO.LOW)

        t0 = time.perf_counter()
        while GPIO.input(self.echo) == 0:
            if time.perf_counter() - t0 > timeout:
                return None
        ini = time.perf_counter()
        while GPIO.input(self.echo) == 1:
            if time.perf_counter() - ini > timeout:
                return None
        dur = time.perf_counter() - ini
        return (dur * VEL_SOM_CM_S) / 2.0

    def ler(self):
        """Devolve a leitura crua (distancia em cm) util ao diagnostico."""
        return self._distancia_cm()

    def _leitura_bruta(self):
        """True/False para o estado da leitura atual, sem debounce."""
        d = self._distancia_cm()
        if d is None:
            return False                 # sem eco confiavel -> assume aberta
        return d <= self.limiar_cm

    def esta_trancada(self):
        """True se o sensor indica porta fechada/trancada (com debounce).

        So propaga uma mudanca de estado apos `debounce_n` leituras
        consecutivas concordando com o novo valor; leituras isoladas
        divergentes (ruido/eco espurio) nao derrubam o estado confirmado.
        """
        leitura = self._leitura_bruta()

        if self._estado_confirmado is None:
            self._estado_confirmado = leitura   # primeira leitura define o estado inicial
            self._candidato = leitura
            self._contagem = self.debounce_n
            return self._estado_confirmado

        if leitura == self._estado_confirmado:
            self._candidato = leitura
            self._contagem = 0
            return self._estado_confirmado

        if leitura == self._candidato:
            self._contagem += 1
        else:
            self._candidato = leitura
            self._contagem = 1

        if self._contagem >= self.debounce_n:
            self._estado_confirmado = self._candidato
            self._contagem = 0

        return self._estado_confirmado

    def cleanup(self):
        GPIO.cleanup()


def main():
    p = argparse.ArgumentParser(description="Teste isolado do sensor de estado da tranca.")
    p.add_argument("--trig", type=int, default=PIN_TRIG_PADRAO, help="GPIO TRIG (ultrassonico).")
    p.add_argument("--echo", type=int, default=PIN_ECHO_PADRAO, help="GPIO ECHO (ultrassonico).")
    p.add_argument("--limiar-cm", type=float, default=LIMIAR_CM_PADRAO,
                   help="Distancia (cm) abaixo da qual a porta e considerada fechada.")
    p.add_argument("--debounce", type=int, default=DEBOUNCE_N_PADRAO,
                   help="Leituras consecutivas p/ confirmar uma transicao de estado.")
    args = p.parse_args()

    s = SensorTranca(trig=args.trig, echo=args.echo, limiar_cm=args.limiar_cm,
                      debounce_n=args.debounce)
    print("==== Teste de Sensor de Tranca (Exp 8) - HC-SR04 ====")
    print(f"     TRIG=GPIO{args.trig} ECHO=GPIO{args.echo}, limiar {args.limiar_cm} cm, debounce {args.debounce}")
    print(">> Abra/feche a porta e observe a transicao (Ctrl+C para sair):\n")

    anterior = None
    try:
        while True:
            trancada = s.esta_trancada()
            if trancada != anterior:
                leitura = s.ler()
                extra = f"{leitura:.1f} cm" if leitura is not None else "sem eco"
                print(f"   estado = {'TRANCADA' if trancada else 'ABERTA':>8}   ({extra})")
                anterior = trancada
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nInterrompido.")
    finally:
        s.cleanup()


if __name__ == "__main__":
    main()
