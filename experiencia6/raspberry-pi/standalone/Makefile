# Makefile - Calculadora binaria standalone em C (Exp 6 - Desafio)
# Freenove Projects Board + wiringPi. A ULA vem do Assembly libalu.s.
#
#   make          -> compila ./calculadora (C + Assembly, linkando wiringPi)
#   make run      -> compila e roda (precisa de sudo p/ GPIO)
#   make clean    -> remove o executavel

CC     = gcc
CFLAGS = -O2 -Wall
LIBS   = -lwiringPi

TARGET = calculadora
SRC    = calculadora.c libalu.s

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) -o $(TARGET) $(SRC) $(LIBS) -l wiringPi

run: $(TARGET)
	sudo ./$(TARGET)

clean:
	rm -f $(TARGET)

.PHONY: all run clean
