# Makefile - Calculadora Binaria ARM64 (Raspberry Pi 3)
# Experiencia 6 - PCS3732
#
# Compila o Assembly puro (as + ld, sem libc).
# Uso:
#   make          -> gera o executavel ./calculadora
#   make run      -> compila e executa
#   make c        -> compila a versao de referencia em C (calculadora_c)
#   make clean    -> remove os artefatos

AS      = as
LD      = ld
CC      = gcc

TARGET  = calculadora
OBJ     = calculadora.o
SRC     = calculadora.s

all: $(TARGET)

$(TARGET): $(OBJ)
	$(LD) -o $(TARGET) $(OBJ)

$(OBJ): $(SRC)
	$(AS) -o $(OBJ) $(SRC)

run: $(TARGET)
	./$(TARGET)

# Versao de referencia em C (portavel; serve para conferir resultados)
c: calculadora_c

calculadora_c: calculadora.c
	$(CC) -O2 -o calculadora_c calculadora.c

clean:
	rm -f $(TARGET) $(OBJ) calculadora_c

.PHONY: all run c clean
