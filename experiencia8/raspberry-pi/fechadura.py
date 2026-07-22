#!/usr/bin/env python3
"""
Fechadura Eletronica - INTEGRACAO (Raspberry Pi 3, PCS3732, Experiencia 8).

Junta os componentes isolados sob uma UNICA maquina de estados NAO-BLOQUEANTE:
  teclado matricial (keypad.py) -> entrada de senha
  display LCD I2C  (lcd_i2c.py) -> feedback de status em tempo real
  buzzer           (buzzer.py)  -> feedback sonoro (sucesso / erro / alerta)
  sensor de tranca (sensor.py)  -> integridade fisica (trancada / aberta)
  atuador          (trava.py)   -> abre/fecha o ferrolho ao validar a senha

Requisitos atendidos (matriz de testes - ver RELATORIO):
  RF01  Entrada de senha numerica pelo teclado (4-6 digitos, com apagar/submeter)
  RF02  LCD exibe o status em tempo real (atualizacao imediata na transicao)
  RF03  Sensor verifica a integridade fisica -> ALARME em abertura forcada
  RF04  Feedback sonoro distinto para sucesso, erro e alerta
  RF05  Acionamento da tranca (servo/rele) ao validar a senha
  RNF01 Confiabilidade: cooldown apos N erros, SEM travar o SO
  RNF02 Nao-bloqueio: a varredura do teclado e o sensor nunca sao congelados
        pelo buzzer (som agendado por tick, laco cooperativo)
  RNF03 Seguranca: senha guardada como HASH (PBKDF2-HMAC-SHA256 + sal), nunca
        em texto plano; comparacao em tempo constante (hmac.compare_digest)
  RNF04 Debouncing das teclas (evento unico por pressao)

ARQUITETURA NAO-BLOQUEANTE (o ponto critico do enunciado): o laco de
monitoramento (idle) NUNCA usa sleep bloqueante. O buzzer toca por agenda
(bz.tick()), o teclado e varrido e o sensor e lido a cada iteracao. As unicas
esperas sao os movimentos discretos do atuador (servo) nas transicoes
abre/fecha - momentaneos e fora do laco de monitoramento.

Seguranca da senha (RNF03): o dispositivo guarda apenas <sal>$<hash>. Em
producao, o hash e gerado OFFLINE e so ele e implantado (o texto plano nunca
toca o Pi). Gere o par com:
    python3 fechadura.py --gerar-hash 2468

Uso:
  python3 fechadura.py                       # PIN padrao, servo + sensor ultrassonico
  python3 fechadura.py --pin 1357
  python3 fechadura.py --hash <sal$hash>     # implanta so o hash (modo producao)
  python3 fechadura.py --sensor-trig 14 --sensor-echo 15
  python3 fechadura.py --trava-tipo rele --trava-pino 18
  python3 fechadura.py --lcd-addr 0x3F
  python3 fechadura.py --sem-lcd             # sem display: espelha status no console
"""

import os
import time
import hmac
import signal
import hashlib
import argparse
import binascii

from keypad import Keypad
from buzzer import Buzzer
from sensor import SensorTranca
from trava import Trava

# ---------------------------------------------------------------------------
# Parametros
# ---------------------------------------------------------------------------
PIN_PADRAO       = "1234"
SENHA_MIN        = 4          # RF01: sequencia de 4 a 6 digitos
SENHA_MAX        = 6
MAX_ERROS        = 3          # RNF01: erros consecutivos antes do bloqueio
T_ABERTA_S       = 4.0        # tempo destrancada antes de re-trancar sozinha
T_BLOQUEIO_S     = 15.0       # cooldown apos MAX_ERROS (RNF01)
T_MSG_S          = 1.5        # tempo exibindo mensagens efemeras (negado/ok)
T_INATIVIDADE_S  = 10.0       # abandona a digitacao apos inatividade
ITERACOES_PBKDF2 = 100_000    # custo do KDF (RNF03) - ver RELATORIO

# Pinos padrao (numeracao BCM) - ver README para a fiacao completa
PIN_BUZZER = 12
PIN_TRAVA  = 18
PIN_SENSOR_TRIG = 14
PIN_SENSOR_ECHO = 15
LIMIAR_CM_PADRAO = 8.0
LCD_ADDR   = 0x27

# Estados da maquina
TRANCADA, DIGITANDO, ABERTA, NEGADO, BLOQUEADO, ALARME = (
    "TRANCADA", "DIGITANDO", "ABERTA", "NEGADO", "BLOQUEADO", "ALARME")


# ---------------------------------------------------------------------------
# Seguranca da senha (RNF03)
# ---------------------------------------------------------------------------
def gerar_hash(pin, sal=None, iteracoes=ITERACOES_PBKDF2):
    """Deriva a senha com PBKDF2-HMAC-SHA256 + sal. Formato: 'sal_hex$hash_hex'."""
    if sal is None:
        sal = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pin.encode(), sal, iteracoes)
    return f"{binascii.hexlify(sal).decode()}${binascii.hexlify(dk).decode()}"


def conferir_pin(pin, guardado, iteracoes=ITERACOES_PBKDF2):
    """Compara o PIN digitado com o hash guardado, em TEMPO CONSTANTE."""
    try:
        sal_hex, hash_hex = guardado.split("$", 1)
        sal = binascii.unhexlify(sal_hex)
        esperado = binascii.unhexlify(hash_hex)
    except (ValueError, binascii.Error):
        return False
    calc = hashlib.pbkdf2_hmac("sha256", pin.encode(), sal, iteracoes)
    return hmac.compare_digest(calc, esperado)   # imune a timing attack


# ---------------------------------------------------------------------------
# Saida de status: LCD I2C (ou console, se --sem-lcd / LCD ausente)
# ---------------------------------------------------------------------------
class SaidaConsole:
    """Fallback quando nao ha LCD: espelha o status no terminal."""
    def __init__(self):
        self._ult = None
    def show(self, l0="", l1=""):
        if (l0, l1) != self._ult:
            print(f"[LCD] {l0:<16} | {l1:<16}")
            self._ult = (l0, l1)
    def close(self):
        pass


def abrir_saida(usar_lcd, addr):
    if not usar_lcd:
        return SaidaConsole()
    try:
        from lcd_i2c import LcdI2c
        return LcdI2c(addr=addr)
    except Exception as e:      # I2C desabilitado / modulo ausente / OSError
        print(f"[aviso] LCD indisponivel ({e}); espelhando status no console.")
        return SaidaConsole()


# ---------------------------------------------------------------------------
# Maquina de estados da fechadura
# ---------------------------------------------------------------------------
class Fechadura:
    def __init__(self, args):
        self.senha_hash = args.hash if args.hash else gerar_hash(args.pin)

        self.kp  = Keypad()
        self.bz  = Buzzer(args.buzzer_pino, setup_gpio=False)
        self.lcd = abrir_saida(not args.sem_lcd, args.lcd_addr)
        self.sensor = SensorTranca(trig=args.sensor_trig, echo=args.sensor_echo,
                                   limiar_cm=args.sensor_limiar_cm, setup_gpio=False)
        self.trava = Trava(tipo=args.trava_tipo, pino=args.trava_pino,
                           setup_gpio=False)

        self.estado = TRANCADA
        self.buffer = ""            # digitos da senha em digitacao
        self.erros = 0
        self.t_estado = time.perf_counter()   # quando entrou no estado atual
        self.t_tecla = 0.0                     # ultima tecla (inatividade)
        self._negado_txt = ("ACESSO NEGADO", "")
        self._ult_lcd = None
        self._running = True

    # -- helpers -------------------------------------------------------------
    def _ir_para(self, estado):
        self.estado = estado
        self.t_estado = time.perf_counter()

    def _lcd(self, l0, l1):
        if (l0, l1) != self._ult_lcd:      # so escreve na mudanca (RF02)
            self.lcd.show(l0, l1)
            self._ult_lcd = (l0, l1)

    def _mascara(self):
        return "*" * len(self.buffer)

    # -- deteccao de violacao fisica (RF03) ---------------------------------
    def _violada(self):
        """Logicamente trancada, mas o sensor diz que a porta esta ABERTA."""
        return self.trava.esta_trancada() and not self.sensor.esta_trancada()

    # -- passo do laco (NAO bloqueia) ---------------------------------------
    def passo(self):
        self.bz.tick()
        agora = time.perf_counter()

        # ALARME tem prioridade sobre tudo, exceto quando ja aberta legitimamente.
        if self.estado not in (ABERTA, ALARME) and self._violada():
            self._entrar_alarme()

        if self.estado == TRANCADA:      self._st_trancada(agora)
        elif self.estado == DIGITANDO:   self._st_digitando(agora)
        elif self.estado == ABERTA:      self._st_aberta(agora)
        elif self.estado == NEGADO:      self._st_negado(agora)
        elif self.estado == BLOQUEADO:   self._st_bloqueado(agora)
        elif self.estado == ALARME:      self._st_alarme(agora)

    # -- estados -------------------------------------------------------------
    def _st_trancada(self, agora):
        self._lcd("== FECHADURA ==", "Digite a senha")
        k = self.kp.get_event()
        if k and k.isdigit():
            self.buffer = k
            self.bz.tecla()
            self.t_tecla = agora
            self._ir_para(DIGITANDO)

    def _st_digitando(self, agora):
        self._lcd(f"Senha: {self._mascara()}", "#=OK  *=apaga")
        if agora - self.t_tecla > T_INATIVIDADE_S:   # desistiu -> volta
            self.buffer = ""
            self._ir_para(TRANCADA)
            return
        k = self.kp.get_event()
        if not k:
            return
        self.t_tecla = agora
        if k.isdigit():
            if len(self.buffer) < SENHA_MAX:
                self.buffer += k
                self.bz.tecla()
        elif k == "*":                       # apagar ultimo digito
            self.buffer = self.buffer[:-1]
            self.bz.tecla()
            if not self.buffer:
                self._ir_para(TRANCADA)
        elif k == "D":                       # cancelar tudo
            self.buffer = ""
            self._ir_para(TRANCADA)
        elif k == "#":                       # submeter
            self._verificar()

    def _verificar(self):
        if not (SENHA_MIN <= len(self.buffer) <= SENHA_MAX):
            self.buffer = ""
            self._negado_txt = ("Senha invalida", f"{SENHA_MIN}-{SENHA_MAX} digitos")
            self.bz.erro()
            self._ir_para(NEGADO)
            return
        ok = conferir_pin(self.buffer, self.senha_hash)
        self.buffer = ""
        if ok:
            self.erros = 0
            self.bz.sucesso()
            self.trava.destrancar()          # RF05: abre o ferrolho
            self._ir_para(ABERTA)
        else:
            self.erros += 1
            restam = max(MAX_ERROS - self.erros, 0)
            self._negado_txt = ("ACESSO NEGADO", f"tentativas: {restam}")
            self.bz.erro()
            self._ir_para(NEGADO)

    def _st_aberta(self, agora):
        if agora - self.t_estado <= T_ABERTA_S:
            self._lcd("ACESSO LIBERADO", "** ABERTO **")
        elif self.sensor.esta_trancada():    # so re-tranca com a porta fechada
            self.trava.trancar()             # (evita travar o ferrolho no vazio)
            self._ir_para(TRANCADA)
        else:
            self._lcd("Feche a porta", "para trancar")

    def _st_negado(self, agora):
        self._lcd(*self._negado_txt)
        if agora - self.t_estado > T_MSG_S:
            if self.erros >= MAX_ERROS:      # RNF01: entra em cooldown
                self._ir_para(BLOQUEADO)
            else:
                self._ir_para(TRANCADA)

    def _st_bloqueado(self, agora):
        falta = int(T_BLOQUEIO_S - (agora - self.t_estado)) + 1
        self._lcd("BLOQUEADO", f"aguarde {falta:>2}s")
        # o teclado e ignorado, mas o laco e o sensor continuam vivos (nao trava o SO)
        self.kp.get_event()                  # drena eventos (sem agir)
        if agora - self.t_estado > T_BLOQUEIO_S:
            self.erros = 0
            self._ir_para(TRANCADA)

    def _entrar_alarme(self):
        self.bz.alerta()
        self._ir_para(ALARME)

    def _st_alarme(self, agora):
        self._lcd("!! ALERTA !!", "PORTA VIOLADA")
        if not self.bz.tocando():
            self.bz.alerta()                 # mantem a sirene enquanto durar
        if not self._violada():              # porta voltou a fechar -> normaliza
            self.bz.off()
            self._ir_para(TRANCADA)

    # -- ciclo de vida -------------------------------------------------------
    def run(self):
        print("==== Fechadura Eletronica (Exp 8) - PCS3732 ====")
        print(f"  Teclado: digitos 0-9 | # submete | * apaga | D cancela")
        print(f"  Senha: {SENHA_MIN}-{SENHA_MAX} digitos | erros p/ bloqueio: {MAX_ERROS}")
        print(f"  Sensor: ultrassonico (HC-SR04) | Tranca: {self.trava.tipo}")
        print("  Ctrl+C para sair.\n")
        signal.signal(signal.SIGINT, self._sair)
        signal.signal(signal.SIGTERM, self._sair)
        try:
            while self._running:
                self.passo()
                time.sleep(0.005)            # intervalo de poll cooperativo (nao bloqueia estado)
        finally:
            self._encerrar()

    def _sair(self, *_):
        self._running = False

    def _encerrar(self):
        self.bz.off()
        try:
            self.lcd.show("Encerrado", "GPIO liberado")
            self.lcd.close()
        except Exception:
            pass
        try:
            self.trava.close()
        except Exception:
            pass
        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup()
        except Exception:
            pass
        print("\nEncerrado. GPIO liberado.")


# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="Fechadura eletronica integrada (RPi 3).")
    p.add_argument("--gerar-hash", metavar="PIN",
                   help="Gera 'sal$hash' PBKDF2 para o PIN e sai (uso offline).")
    p.add_argument("--pin", default=PIN_PADRAO, help=f"PIN inicial (padrao {PIN_PADRAO}).")
    p.add_argument("--hash", default=None,
                   help="Hash guardado 'sal$hash' (modo producao: sem texto plano).")
    p.add_argument("--sensor-trig", type=int, default=PIN_SENSOR_TRIG)
    p.add_argument("--sensor-echo", type=int, default=PIN_SENSOR_ECHO)
    p.add_argument("--sensor-limiar-cm", type=float, default=LIMIAR_CM_PADRAO)
    p.add_argument("--trava-tipo", choices=["servo", "rele"], default="servo")
    p.add_argument("--trava-pino", type=int, default=PIN_TRAVA)
    p.add_argument("--buzzer-pino", type=int, default=PIN_BUZZER)
    p.add_argument("--lcd-addr", type=lambda x: int(x, 0), default=LCD_ADDR)
    p.add_argument("--sem-lcd", action="store_true", help="Roda sem LCD (status no console).")
    args = p.parse_args()

    if args.gerar_hash:
        print(gerar_hash(args.gerar_hash))
        return

    Fechadura(args).run()


if __name__ == "__main__":
    main()
