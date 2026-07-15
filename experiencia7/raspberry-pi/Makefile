# Makefile - Metronomo PWM (Raspberry Pi 3)
# Experiencia 7 - PCS3732
#
# Uso:
#   make run             -> roda o metronomo (60 BPM)
#   make run-silencioso  -> roda com o buzzer desligado
#   make install         -> instala a dependencia RPi.GPIO
#   make clean           -> remove caches do Python

PYTHON = python3
SRC    = metronomo.py

run:
	$(PYTHON) $(SRC)

run-silencioso:
	$(PYTHON) $(SRC) --no-buzzer

install:
	sudo apt update && sudo apt install -y python3-rpi.gpio

clean:
	rm -rf __pycache__ *.pyc

.PHONY: run run-silencioso install clean
