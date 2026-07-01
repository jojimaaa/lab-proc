# Makefile - ULA em Assembly como biblioteca compartilhada (Exp 6 - Desafio)
#
#   make        -> compila libalu.so (a partir de libalu.s)
#   make run    -> compila e roda a calculadora (precisa do hardware ligado)
#   make clean  -> remove a lib

CC = gcc

all: libalu.so

libalu.so: libalu.s
	$(CC) -shared -fPIC -o libalu.so libalu.s

run: libalu.so
	python3 calculadora.py

clean:
	rm -f libalu.so

.PHONY: all run clean
