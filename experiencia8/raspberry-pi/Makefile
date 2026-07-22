# Makefile - Fechadura Eletronica (Raspberry Pi 3)
# Experiencia 8 - PCS3732
#
# Uso:
#   make run              -> fechadura integrada (servo + sensor ultrassonico + LCD)
#   make run-sem-lcd      -> integrada sem LCD (status espelhado no console)
#   make test-keypad      -> teste isolado do teclado matricial 4x4
#   make test-lcd         -> teste isolado do LCD I2C (Hello World)
#   make test-buzzer      -> teste isolado do buzzer (sucesso/erro/alerta)
#   make test-sensor      -> teste isolado do sensor de tranca
#   make test-trava       -> teste isolado do atuador (servo/rele)
#   make i2c              -> lista dispositivos no barramento I2C (i2cdetect)
#   make gerar-hash       -> imprime 'sal$$hash' do PIN (PIN=xxxx)
#   make install          -> instala dependencias (RPi.GPIO, smbus, i2c-tools)
#   make clean            -> remove caches do Python

PYTHON = python3
PIN   ?= 2468

run:
	$(PYTHON) fechadura.py

run-sem-lcd:
	$(PYTHON) fechadura.py --sem-lcd

test-keypad:
	$(PYTHON) keypad.py

test-lcd:
	$(PYTHON) lcd_i2c.py

test-buzzer:
	$(PYTHON) buzzer.py

test-sensor:
	$(PYTHON) sensor.py

test-trava:
	$(PYTHON) trava.py

i2c:
	i2cdetect -y 1

gerar-hash:
	$(PYTHON) fechadura.py --gerar-hash $(PIN)

install:
	sudo apt update && sudo apt install -y python3-rpi.gpio python3-smbus i2c-tools

clean:
	rm -rf __pycache__ *.pyc

.PHONY: run run-sem-lcd test-keypad test-lcd test-buzzer \
        test-sensor test-trava i2c gerar-hash install clean
