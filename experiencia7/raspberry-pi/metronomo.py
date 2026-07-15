#!/usr/bin/env python3
"""
Metronomo com Temporizacao e PWM - Raspberry Pi 3 (PCS3732, Experiencia 7)

Requisitos atendidos (matriz de testes do enunciado):
  RF01  Temporizacao 1 Hz .... batida precisa com correcao de drift (jitter < 5 ms)
  RF02  Controle de BPM ....... 2 botoes alteram o andamento em tempo real
  RF03  Modulacao PWM ......... servo varre o angulo + LED com brilho em rampa
  RNF01 Debouncing fisico ..... GPIO.add_event_detect(..., bouncetime=200)

Arquitetura de software (multiplexacao - ver diagrama do enunciado):
  - Thread PRINCIPAL   : laco do metronomo (temporizacao critica de 1 Hz).
  - Callbacks (ISR)    : escuta dos botoes por borda de descida. Rodam em uma
                         thread separada criada pelo RPi.GPIO e SO atualizam uma
                         variavel global (o BPM). Assim o laco de temporizacao
                         nunca fica bloqueado esperando o hardware fisico.
"""

import time
import threading
import signal
import argparse

try:
    import RPi.GPIO as GPIO
except (ImportError, RuntimeError):
    raise SystemExit(
        "Este programa precisa rodar em um Raspberry Pi com a biblioteca "
        "RPi.GPIO instalada (pip install RPi.GPIO)."
    )

# ---------------------------------------------------------------------------
# Mapa de pinos (numeracao BCM) - ver README.md para a fiacao
# ---------------------------------------------------------------------------
# Botoes coloridos da Freenove Projects Board (active-low: pressionado = LOW).
# A ordem abaixo casa com a cor que voce preferir - basta trocar os numeros.
PIN_BTN_UP     = 26   # botao: aumenta o BPM
PIN_BTN_DOWN   = 20   # botao: diminui o BPM
PIN_BTN_BUZZER = 16   # botao: liga/desliga o som (buzzer configuravel)
PIN_BTN_PLAY   = 21   # botao: pausa / retoma o metronomo

PIN_LED      = 17   # LED de status (PWM, atraves de resistor 330 ohm) [HW PWM0]
PIN_SERVO    = 18   # servomotor SG90 (sinal PWM 50 Hz)                [HW PWM0]
PIN_BUZZER   = 12   # buzzer (sinal digital on/off)

# ---------------------------------------------------------------------------
# Parametros
# ---------------------------------------------------------------------------
BPM_MIN, BPM_MAX = 30, 240
BPM_STEP         = 5
BPM_INICIAL      = 60          # 60 BPM = 1 Hz = periodo de 1000 ms (RF01)

LED_FREQ_HZ    = 1000          # 1 kHz -> persistencia de visao (sem cintilar)
SERVO_FREQ_HZ  = 50            # 50 Hz -> periodo de 20 ms (base do SG90)
BUZZER_BEEP_S  = 0.03          # duracao do "tique" sonoro por batida
FADE_STEPS     = 40            # passos da rampa de brilho do LED entre batidas

# Servo: largura de pulso -> duty cycle (periodo 20 ms)
#   1.0 ms ->  5.0 % ->   0 graus  (pendulo a esquerda)
#   1.5 ms ->  7.5 % ->  90 graus
#   2.0 ms -> 10.0 % -> 180 graus  (pendulo a direita)
SERVO_DUTY_ESQ = 5.0
SERVO_DUTY_DIR = 10.0

DEBOUNCE_MS = 200              # RNF01: janela de rejeicao de ruido mecanico

# ---------------------------------------------------------------------------
# Estado compartilhado entre a thread principal e os callbacks (protegido)
# ---------------------------------------------------------------------------
_lock = threading.Lock()
_bpm = BPM_INICIAL
_buzzer_ligado = True
_ativo = True                 # play/pause (botao GPIO21)
_running = True


def periodo_s():
    """Periodo (s) de uma batida a partir do BPM atual, de forma thread-safe."""
    with _lock:
        return 60.0 / _bpm


def ajustar_bpm(delta):
    """Incremento/decremento linear do BPM, saturando nos limites (RF02)."""
    global _bpm
    with _lock:
        _bpm = max(BPM_MIN, min(BPM_MAX, _bpm + delta))
        atual = _bpm
    print(f"> BPM alterado para {atual}")


# ---------------------------------------------------------------------------
# Callbacks dos botoes (rodam na thread de eventos do RPi.GPIO).
# So atualizam estado compartilhado - nunca bloqueiam o laco do metronomo.
# ---------------------------------------------------------------------------
def _cb_up(channel):
    ajustar_bpm(+BPM_STEP)


def _cb_down(channel):
    ajustar_bpm(-BPM_STEP)


def _cb_buzzer(channel):
    global _buzzer_ligado
    with _lock:
        _buzzer_ligado = not _buzzer_ligado
        estado = _buzzer_ligado
    print(f"> Som {'ligado' if estado else 'desligado'}")


def _cb_play(channel):
    global _ativo
    with _lock:
        _ativo = not _ativo
        estado = _ativo
    print(f"> Metronomo {'tocando' if estado else 'pausado'}")


# ---------------------------------------------------------------------------
# Setup / teardown de hardware
# ---------------------------------------------------------------------------
def setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # Botoes coloridos da Freenove: active-low. Pull-up interno; pressionar leva
    # o pino de 3.3V a 0V -> BORDA DE DESCIDA -> GPIO.FALLING.
    for pino in (PIN_BTN_UP, PIN_BTN_DOWN, PIN_BTN_BUZZER, PIN_BTN_PLAY):
        GPIO.setup(pino, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    # Atuadores
    GPIO.setup(PIN_LED,    GPIO.OUT)
    GPIO.setup(PIN_SERVO,  GPIO.OUT)
    GPIO.setup(PIN_BUZZER, GPIO.OUT, initial=GPIO.LOW)

    led   = GPIO.PWM(PIN_LED,   LED_FREQ_HZ)
    servo = GPIO.PWM(PIN_SERVO, SERVO_FREQ_HZ)
    led.start(0)
    servo.start(0)

    # RNF01: debouncing por software. A flag do controlador ignora interrupcoes
    # subsequentes por 'bouncetime' ms apos o primeiro gatilho.
    GPIO.add_event_detect(PIN_BTN_UP,     GPIO.FALLING,
                          callback=_cb_up,     bouncetime=DEBOUNCE_MS)
    GPIO.add_event_detect(PIN_BTN_DOWN,   GPIO.FALLING,
                          callback=_cb_down,   bouncetime=DEBOUNCE_MS)
    GPIO.add_event_detect(PIN_BTN_BUZZER, GPIO.FALLING,
                          callback=_cb_buzzer, bouncetime=DEBOUNCE_MS)
    GPIO.add_event_detect(PIN_BTN_PLAY,   GPIO.FALLING,
                          callback=_cb_play,   bouncetime=DEBOUNCE_MS)

    return led, servo


def _fade_led(led, restante):
    """Rampa de brilho do LED (100% -> 0%) preenchendo EXATAMENTE o intervalo
    entre batidas. Como a soma dos passos == 'restante', a temporizacao do
    metronomo continua precisa (RF01) e ao mesmo tempo ha modulacao PWM
    visivel e suave (RF03)."""
    if restante <= 0:
        led.ChangeDutyCycle(0)
        return
    passo = restante / FADE_STEPS
    for i in range(FADE_STEPS):
        if not _running:            # sai na hora ao receber Ctrl+C
            break
        duty = 100.0 * (1.0 - (i + 1) / FADE_STEPS)   # 100 -> 0
        led.ChangeDutyCycle(duty)
        time.sleep(passo)


# ---------------------------------------------------------------------------
# Laco principal do metronomo (thread principal)
# ---------------------------------------------------------------------------
def loop_metronomo(led, servo):
    lado_direito = False
    # Agenda ABSOLUTA: 'proximo' acumula periodos exatos, independente do tempo
    # gasto processando cada batida. Isso elimina o acumulo de erro (drift) que
    # o simples time.sleep(periodo) produziria. Equivale ao "Sleep Delta"
    # (sleep = periodo - tempo_de_execucao_do_laco) do enunciado, porem imune a
    # acumulo ao longo de muitas batidas.
    proximo = time.perf_counter()

    while _running:
        # ---- play/pause (botao GPIO21) --------------------------------
        with _lock:
            ativo = _ativo
        if not ativo:
            GPIO.output(PIN_BUZZER, GPIO.LOW)
            led.ChangeDutyCycle(0)
            servo.ChangeDutyCycle(0)     # solta o servo enquanto pausado
            time.sleep(0.05)
            proximo = time.perf_counter()  # ao retomar, recomeca sem "correr atras"
            continue

        # ---- instante da batida ---------------------------------------
        # 1) Servo: alterna o "pendulo" entre dois angulos (RF03 - varredura).
        lado_direito = not lado_direito
        servo.ChangeDutyCycle(SERVO_DUTY_DIR if lado_direito else SERVO_DUTY_ESQ)

        # 2) LED: acende no maximo - inicio da rampa de brilho.
        led.ChangeDutyCycle(100)

        # 3) Buzzer: tique sonoro na batida (RF01), se habilitado.
        with _lock:
            beep = _buzzer_ligado
        if beep:
            GPIO.output(PIN_BUZZER, GPIO.HIGH)
            time.sleep(BUZZER_BEEP_S)
            GPIO.output(PIN_BUZZER, GPIO.LOW)

        # ---- intervalo ate a proxima batida ---------------------------
        proximo += periodo_s()
        restante = proximo - time.perf_counter()
        if restante < 0:
            # atraso (ex.: BPM subiu muito): re-sincroniza sem acumular erro.
            proximo = time.perf_counter()
            restante = 0.0

        _fade_led(led, restante)

    # saida limpa: solta o servo e apaga o LED
    servo.ChangeDutyCycle(0)
    led.ChangeDutyCycle(0)


# ---------------------------------------------------------------------------
# Encerramento
# ---------------------------------------------------------------------------
def _sair(signum, frame):
    global _running
    _running = False


def main():
    global _bpm, _buzzer_ligado

    parser = argparse.ArgumentParser(
        description="Metronomo com temporizacao precisa e PWM no Raspberry Pi 3."
    )
    parser.add_argument("--bpm", type=int, default=BPM_INICIAL,
                        help=f"BPM inicial ({BPM_MIN}-{BPM_MAX}). Padrao: {BPM_INICIAL}.")
    parser.add_argument("--no-buzzer", action="store_true",
                        help="Inicia com o buzzer desligado (sinal sonoro configuravel).")
    args = parser.parse_args()

    _bpm = max(BPM_MIN, min(BPM_MAX, args.bpm))
    _buzzer_ligado = not args.no_buzzer

    signal.signal(signal.SIGINT, _sair)
    signal.signal(signal.SIGTERM, _sair)

    led, servo = setup()
    print("==== Metronomo PWM (Exp 7) - PCS3732 ====")
    print(f"BPM inicial: {_bpm}  |  som: {'ligado' if _buzzer_ligado else 'desligado'}")
    print("Botoes (Freenove):")
    print(f"  GPIO{PIN_BTN_UP} = +{BPM_STEP} BPM     GPIO{PIN_BTN_DOWN} = -{BPM_STEP} BPM")
    print(f"  GPIO{PIN_BTN_BUZZER} = liga/desliga som   GPIO{PIN_BTN_PLAY} = pausa/retoma")
    print("Ctrl+C para sair.\n")
    try:
        loop_metronomo(led, servo)
    finally:
        led.stop()
        servo.stop()
        GPIO.output(PIN_BUZZER, GPIO.LOW)
        GPIO.cleanup()
        print("\nEncerrado. GPIO liberado.")


if __name__ == "__main__":
    main()
