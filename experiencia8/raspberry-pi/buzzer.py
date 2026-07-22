#!/usr/bin/env python3
"""
Controle ISOLADO do buzzer (feedback sonoro de sucesso / erro / alerta).
Experiencia 8 (PCS3732) - item "Implemente isoladamente o controle de cada
componente" -> aqui o BUZZER (RF04: feedback sonoro).

Buzzer ATIVO: tem oscilador interno; basta nivel logico ALTO para apitar
(controle digital on/off). E o caso do diagrama do enunciado ("Sinal Digital").

PONTO-CHAVE DE ARQUITETURA (enunciado, "Codigo Bloqueante"): usar time.sleep()
para dar duracao ao bipe CONGELA a varredura do teclado e o monitoramento do
sensor. Por isso esta classe oferece um modo NAO-BLOQUEANTE: play(padrao) agenda
uma sequencia de segmentos (ligado/desligado, em segundos) e tick() avanca essa
agenda a cada iteracao do laco principal, sem nunca bloquear. O relogio usado e
o monotonico time.perf_counter() (imune a ajustes do relogio de parede).

Uso:
  python3 buzzer.py                 # toca sucesso, erro e alerta (demo)
  python3 buzzer.py --pino 12
"""

import time
import argparse

try:
    import RPi.GPIO as GPIO
except (ImportError, RuntimeError):
    raise SystemExit("Rode em um Raspberry Pi com RPi.GPIO instalado.")

PIN_BUZZER_PADRAO = 12

# Padroes (segmentos: (ligado?, duracao_s)) - a semantica sonora da fechadura.
PADRAO_SUCESSO = [(True, 0.08), (False, 0.06), (True, 0.08)]        # 2 bipes curtos
PADRAO_ERRO    = [(True, 0.60)]                                     # 1 bipe longo
PADRAO_TECLA   = [(True, 0.02)]                                     # clique de tecla
PADRAO_ALERTA  = [(True, 0.15), (False, 0.15)] * 6                  # sirene intermitente


class Buzzer:
    """Buzzer ativo com reproducao nao-bloqueante de padroes."""

    def __init__(self, pino=PIN_BUZZER_PADRAO, setup_gpio=True):
        self.pino = pino
        if setup_gpio:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
        GPIO.setup(self.pino, GPIO.OUT, initial=GPIO.LOW)
        self._seq = []              # lista de segmentos pendentes
        self._fim_seg = 0.0         # instante de fim do segmento atual
        self._ligado = False

    def _set(self, ligado):
        self._ligado = ligado
        GPIO.output(self.pino, GPIO.HIGH if ligado else GPIO.LOW)

    # -- modo NAO-BLOQUEANTE (usado na integracao / fechadura.py) ------------
    def play(self, padrao):
        """Agenda um padrao (interrompe o anterior)."""
        self._seq = list(padrao)
        self._fim_seg = 0.0         # forca o tick a iniciar o 1o segmento ja
        self._avanca_segmento(time.perf_counter())

    def _avanca_segmento(self, agora):
        if not self._seq:
            self._set(False)
            return
        ligado, dur = self._seq.pop(0)
        self._set(ligado)
        self._fim_seg = agora + dur

    def tick(self):
        """Chame a cada iteracao do laco. Avanca a agenda do som se preciso."""
        if not self._seq and not self._ligado:
            return
        agora = time.perf_counter()
        if agora >= self._fim_seg:
            self._avanca_segmento(agora)

    def tocando(self):
        return bool(self._seq) or self._ligado

    # atalhos semanticos
    def sucesso(self):  self.play(PADRAO_SUCESSO)
    def erro(self):     self.play(PADRAO_ERRO)
    def tecla(self):    self.play(PADRAO_TECLA)
    def alerta(self):   self.play(PADRAO_ALERTA)

    # -- modo BLOQUEANTE (util so no teste isolado) --------------------------
    def bipe(self, dur_on=0.1, dur_off=0.1, n=1):
        for _ in range(n):
            self._set(True);  time.sleep(dur_on)
            self._set(False); time.sleep(dur_off)

    def off(self):
        self._seq = []
        self._set(False)

    def cleanup(self):
        self.off()
        GPIO.cleanup()


def _demo_bloqueante(bz, padrao, nome):
    """Reproduz um padrao usando o proprio agendador (via tick), so para o
    teste isolado poder rodar sem um laco externo."""
    print(f"    {nome}")
    bz.play(padrao)
    while bz.tocando():
        bz.tick()
        time.sleep(0.005)


def main():
    p = argparse.ArgumentParser(description="Teste isolado do buzzer (feedback sonoro).")
    p.add_argument("--pino", type=int, default=PIN_BUZZER_PADRAO, help="GPIO (BCM) do buzzer.")
    args = p.parse_args()

    bz = Buzzer(args.pino)
    print(f"==== Teste de Buzzer (Exp 8) - GPIO{args.pino} ====")
    try:
        _demo_bloqueante(bz, PADRAO_TECLA,   "clique de tecla")
        time.sleep(0.4)
        _demo_bloqueante(bz, PADRAO_SUCESSO, "SUCESSO (2 bipes curtos)")
        time.sleep(0.4)
        _demo_bloqueante(bz, PADRAO_ERRO,    "ERRO (1 bipe longo)")
        time.sleep(0.4)
        _demo_bloqueante(bz, PADRAO_ALERTA,  "ALERTA (sirene intermitente)")
        print("\nConcluido.")
    except KeyboardInterrupt:
        print("\nInterrompido.")
    finally:
        bz.cleanup()


if __name__ == "__main__":
    main()
