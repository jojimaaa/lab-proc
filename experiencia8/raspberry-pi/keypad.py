#!/usr/bin/env python3
"""
Controle ISOLADO do teclado matricial 4x4 (entrada de senha).
Experiencia 8 (PCS3732) - item "Implemente isoladamente o controle de cada
componente" -> aqui o TECLADO MATRICIAL (RF01: entrada de credenciais).

Reaproveita a varredura validada na Experiencia 6 (Freenove Projects Board),
agora em Python/RPi.GPIO e com uma classe NAO-BLOQUEANTE, adequada ao laco de
estados da fechadura (fechadura.py).

VARREDURA (PULL-DOWN, ativo-alto):
  - Linhas (ROWS) sao SAIDAS; em repouso ficam em LOW e sao levadas a HIGH uma
    de cada vez durante a varredura.
  - Colunas (COLS) sao ENTRADAS com PULL-DOWN (repouso = 0); ao pressionar uma
    tecla, a linha em HIGH "atravessa" para a coluna, que passa a ler 1.
  Esse esquema casa com o chip do RPi (GPIO13/19 ja nascem em pull-down) e evita
  colunas flutuando. Ver README (fixar pull-down de GPIO5/6 no config.txt).

DEBOUNCE (RNF04): repique mecanico de contato dura alguns ms. A classe so emite
UM evento por pressao fisica (deteccao de borda + janela de rejeicao), sem nunca
bloquear o laco principal.

Uso:
  python3 keypad.py                # diagnostico de repouso + eco das teclas
  python3 keypad.py --diag         # so o diagnostico das colunas em repouso
"""

import time
import argparse

try:
    import RPi.GPIO as GPIO
except (ImportError, RuntimeError):
    raise SystemExit("Rode em um Raspberry Pi com RPi.GPIO instalado.")

# ---------------------------------------------------------------------------
# Mapa de pinos (numeracao BCM) - identico ao validado na Experiencia 6
# ---------------------------------------------------------------------------
ROWS = [16, 20, 21, 26]     # saidas (linhas)
COLS = [19, 13, 6, 5]       # entradas (colunas), em pull-down
KEYS = [
    ['1', '2', '3', 'A'],
    ['4', '5', '6', 'B'],
    ['7', '8', '9', 'C'],
    ['*', '0', '#', 'D'],
]

SETTLE_US   = 50            # tempo p/ a linha estabilizar antes de ler colunas
DEBOUNCE_MS = 40            # janela de rejeicao de repique por tecla (RNF04)


class Keypad:
    """Teclado matricial 4x4 com varredura pull-down e eventos nao-bloqueantes.

    Uso tipico no laco de estados:
        kp = Keypad()
        while ...:
            tecla = kp.get_event()   # None, ou o caractere pressionado 1x
            ...
        kp.cleanup()
    """

    def __init__(self, rows=ROWS, cols=COLS, keys=KEYS, debounce_ms=DEBOUNCE_MS,
                 setup_gpio=True):
        self.rows, self.cols, self.keys = rows, cols, keys
        self.debounce = debounce_ms / 1000.0
        self._held = None            # tecla considerada "pressionada" agora
        self._t_release = 0.0        # instante da ultima soltura
        if setup_gpio:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
        for r in self.rows:
            GPIO.setup(r, GPIO.OUT, initial=GPIO.LOW)
        for c in self.cols:
            GPIO.setup(c, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    # -- varredura crua: uma passada pela matriz, devolve a tecla ou None -----
    def scan_raw(self):
        for ri, r in enumerate(self.rows):
            GPIO.output(r, GPIO.HIGH)
            time.sleep(SETTLE_US / 1_000_000.0)
            for ci, c in enumerate(self.cols):
                if GPIO.input(c) == GPIO.HIGH:
                    GPIO.output(r, GPIO.LOW)
                    return self.keys[ri][ci]
            GPIO.output(r, GPIO.LOW)
        return None

    # -- evento nao-bloqueante: 1 caractere por pressao fisica ---------------
    def get_event(self):
        """Chame com frequencia. Retorna o caractere UMA vez, na borda de
        pressao (ja com debounce por soltura); caso contrario, None. Nunca
        bloqueia."""
        k = self.scan_raw()
        agora = time.perf_counter()
        if k is not None:
            if self._held is None and (agora - self._t_release) >= self.debounce:
                self._held = k          # nova pressao -> emite um evento
                return k
            return None                 # ainda segurando a mesma tecla
        # nenhuma tecla pressionada agora
        if self._held is not None:
            self._held = None
            self._t_release = agora
        return None

    # -- versao BLOQUEANTE (util so em testes isolados) ----------------------
    def getkey_blocking(self):
        while True:
            k = self.scan_raw()
            if k:
                time.sleep(0.03)
                while self.scan_raw():
                    time.sleep(0.01)    # espera soltar
                return k
            time.sleep(0.005)

    def diagnostico_repouso(self):
        """Sem tecla pressionada, TODAS as colunas devem ler 0. Se alguma ler 1,
        o pull-down daquela coluna nao pegou (ver README: config.txt)."""
        print("== Diagnostico (NAO aperte nada agora) ==")
        suspeita = False
        for c in self.cols:
            v = GPIO.input(c)
            aviso = "  <-- DEVERIA SER 0! (pull-down nao pegou)" if v == 1 else ""
            print(f"  coluna GPIO{c:>2} em repouso = {v}{aviso}")
            suspeita = suspeita or (v == 1)
        if suspeita:
            print("\n>> Alguma coluna leu 1 sem tecla: pull-down inativo nela.")
            print(">> Fixe no /boot/firmware/config.txt:  gpio=5,6,13,19=ip,pd\n")
        else:
            print("\n>> Repouso OK (tudo em 0).\n")
        return not suspeita

    def cleanup(self):
        for r in self.rows:
            GPIO.output(r, GPIO.LOW)
        GPIO.cleanup()


def main():
    p = argparse.ArgumentParser(description="Teste isolado do teclado matricial 4x4.")
    p.add_argument("--diag", action="store_true",
                   help="So o diagnostico de repouso das colunas.")
    args = p.parse_args()

    kp = Keypad()
    print(f"==== Teste de Teclado Matricial (Exp 8) - PCS3732 ====")
    print(f"     linhas (saidas)  BCM: {ROWS}")
    print(f"     colunas (entrada) BCM: {COLS}\n")
    try:
        kp.diagnostico_repouso()
        if args.diag:
            return
        print(">> Pressione teclas (Ctrl+C para sair):\n")
        while True:
            k = kp.get_event()
            if k is not None:
                print(f"   tecla = '{k}'")
            time.sleep(0.005)
    except KeyboardInterrupt:
        print("\nInterrompido.")
    finally:
        kp.cleanup()


if __name__ == "__main__":
    main()
