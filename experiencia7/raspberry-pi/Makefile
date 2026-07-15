# Makefile - Metronomo PWM (Raspberry Pi 3)
# Experiencia 7 - PCS3732
#
# Uso:
#   make run             -> roda o metronomo integrado (60 BPM)
#   make run-silencioso  -> roda com o buzzer desligado
#   make test-led        -> teste isolado do LED (duty + frequencias)
#   make test-servo      -> teste isolado do servomotor
#   make test-buzzer     -> teste isolado do buzzer
#   make install         -> instala a dependencia RPi.GPIO
#   make clean           -> remove caches do Python

PYTHON = python3
SRC    = metronomo.py

run:
	$(PYTHON) $(SRC)

run-silencioso:
	$(PYTHON) $(SRC) --no-buzzer

test-led:
	$(PYTHON) led_pwm.py

test-servo:
	$(PYTHON) servo.py

test-buzzer:
	$(PYTHON) buzzer.py

install:
	sudo apt update && sudo apt install -y python3-rpi.gpio

clean:
	rm -rf __pycache__ *.pyc

.PHONY: run run-silencioso test-led test-servo test-buzzer install clean
