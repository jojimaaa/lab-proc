#!/usr/bin/env python3
"""
calculadora.py - Calculadora binaria STANDALONE (Experiencia 6 - Desafio).

Entrada: teclado matricial 4x4 (GPIO).   Saida: LCD 16x2 (I2C).
A aritmetica (ULA) e executada pela biblioteca ARM64 libalu.so (Assembly),
chamada via ctypes -- o Python cuida apenas das bordas de hardware.

Rode:  python3 calculadora.py     (compile antes a lib:  make)

Mapa do teclado:
    0, 1 -> digitos binarios          A -> +     C -> *
    *    -> ! (fatorial)              B -> -     D -> /
    #    -> = (calcular)              2 -> limpar / novo calculo
"""
import os
import ctypes

from lcd_i2c import LcdI2C
from keypad import Keypad

LCD_ADDR = 0x27          # troque p/ 0x3F se 'i2cdetect -y 1' mostrar esse
MAX_BITS = 4             # entradas de 4 bits (0..15)

# ---- carrega a ULA em Assembly (libalu.so) ----
_here = os.path.dirname(os.path.abspath(__file__))
_lib = ctypes.CDLL(os.path.join(_here, "libalu.so"))
_lib.alu_calc.argtypes = [ctypes.c_int, ctypes.c_int64, ctypes.c_int64,
                          ctypes.POINTER(ctypes.c_int64), ctypes.POINTER(ctypes.c_int64)]
_lib.alu_calc.restype = ctypes.c_int

OP_KEYS = {'A': '+', 'B': '-', 'C': '*', 'D': '/', '*': '!'}


def alu(op, a, b):
    """Chama a ULA em Assembly. Retorna (status, resultado, resto).
    status: 0=OK  1=div/0  2=overflow  3=operacao invalida."""
    res = ctypes.c_int64()
    rem = ctypes.c_int64()
    status = _lib.alu_calc(ord(op), a, b, ctypes.byref(res), ctypes.byref(rem))
    return status, res.value, rem.value


def line(lcd, row, text):
    """Escreve uma linha inteira (preenche/corta em 16 colunas)."""
    lcd.write(text.ljust(16)[:16], row, 0)


def expr_str(a_bits, op, b_bits):
    s = a_bits or "?"
    if op:
        s += " " + op
        if op != '!':
            s += " " + (b_bits or "?")
    return s


def fmt_result(op, res, rem):
    if op == '/':
        s = f"q={res} r={rem}"
    else:
        sign = '-' if res < 0 else ''
        s = f"={res} b{sign}{bin(abs(res))[2:]}"
    if len(s) > 16:                       # nao cabe binario -> so decimal
        s = f"={res}"[:16]
    return s


def run_once(lcd, kp):
    """Um calculo completo: monta A, operacao, B, mostra resultado."""
    a_bits, op, b_bits = "", None, ""
    line(lcd, 0, expr_str(a_bits, op, b_bits))
    line(lcd, 1, "0/1  op:A-D")

    while True:
        k = kp.get_key()
        if k == '2':                      # limpar / recomecar
            return

        if op is None:                    # montando A ou escolhendo a operacao
            if k in '01' and len(a_bits) < MAX_BITS:
                a_bits += k
            elif k in OP_KEYS and a_bits:
                op = OP_KEYS[k]
                line(lcd, 1, "# calcular" if op == '!' else "0/1 B  # calcular")
            else:
                continue
        elif op != '!':                   # montando B
            if k in '01' and len(b_bits) < MAX_BITS:
                b_bits += k
            elif k == '#' and b_bits:
                break
            else:
                continue
        else:                             # fatorial: so espera '#'
            if k == '#':
                break
            continue

        line(lcd, 0, expr_str(a_bits, op, b_bits))

    # ---- calcular via ULA em Assembly ----
    a = int(a_bits, 2)
    b = int(b_bits, 2) if b_bits else 0
    status, res, rem = alu(op, a, b)

    if status == 1:
        line(lcd, 1, "ERRO: div por 0")
    elif status == 2:
        line(lcd, 1, "ERRO: overflow")
    elif status == 3:
        line(lcd, 1, "ERRO: operacao")
    else:
        line(lcd, 1, fmt_result(op, res, rem))

    kp.get_key()                          # qualquer tecla volta ao inicio


def main():
    lcd = LcdI2C(addr=LCD_ADDR)
    kp = Keypad()
    lcd.clear()
    line(lcd, 0, "Calc Bin ARM")
    line(lcd, 1, "Exp6 - Desafio")
    try:
        while True:
            run_once(lcd, kp)
    except KeyboardInterrupt:
        pass
    finally:
        lcd.clear()
        line(lcd, 0, "Ate a proxima")
        kp.cleanup()


if __name__ == "__main__":
    main()
