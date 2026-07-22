#!/usr/bin/env python3
"""
Controle ISOLADO do display LCD 16x2 (HD44780) via I2C (expansor PCF8574).
Experiencia 8 (PCS3732) - item "Implemente isoladamente o controle de cada
componente" -> aqui o DISPLAY LCD (RF02: feedback de status em tempo real).

Por que I2C? O LCD paralelo do HD44780 precisaria de 6+ GPIOs (RS, EN, D4-D7).
O backpack PCF8574 e um expansor de 8 bits que fala I2C, entao o Pi usa APENAS
2 fios (SDA=GPIO2, SCL=GPIO3) para todo o display, liberando GPIOs para o
teclado, o buzzer, o sensor e a tranca (justificativa de arquitetura no
RELATORIO, Secao 8).

Mapeamento dos 8 bits do PCF8574 -> pinos do HD44780 (backpack tipico):
    P0=RS  P1=RW  P2=EN  P3=Backlight  P4..P7=D4..D7 (barramento de 4 bits)
Por isso o driver envia cada byte em DOIS nibbles (interface de 4 bits) e usa
um "strobe" no pino EN para o HD44780 latch-ar cada nibble.

Descubra o endereco do seu modulo com:  i2cdetect -y 1   (tipico: 0x27 ou 0x3F)

Uso:
  python3 lcd_i2c.py                       # escreve "Hello World" (teste isolado)
  python3 lcd_i2c.py --addr 0x3F
  python3 lcd_i2c.py --linha0 "Fechadura" --linha1 "PCS3732 Exp8"
"""

import time
import argparse

# smbus (padrao do Raspberry Pi OS) ou smbus2 como alternativa.
try:
    import smbus
    _SMBus = smbus.SMBus
except ImportError:
    try:
        from smbus2 import SMBus as _SMBus
    except ImportError:
        raise SystemExit(
            "Instale a biblioteca I2C:  sudo apt install python3-smbus\n"
            "                  (ou:     pip install smbus2)"
        )

I2C_BUS_PADRAO = 1          # /dev/i2c-1 -> SDA=GPIO2, SCL=GPIO3 no RPi 3
LCD_ADDR_PADRAO = 0x27      # troque p/ 0x3F conforme 'i2cdetect -y 1'

# Bits de controle do backpack (mascarados no byte enviado ao PCF8574)
LCD_RS = 0x01               # 0 = comando, 1 = dado (caractere)
LCD_EN = 0x04               # enable (strobe)
LCD_BL = 0x08               # backlight (luz de fundo) ligado

# Comandos HD44780
LCD_CLEAR      = 0x01
LCD_HOME       = 0x02
LINHA_OFFSET   = [0x00, 0x40]   # inicio da linha 0 e da linha 1 (DDRAM)


class LcdI2c:
    """Driver HD44780 sobre PCF8574 (I2C), interface de 4 bits."""

    def __init__(self, addr=LCD_ADDR_PADRAO, bus=I2C_BUS_PADRAO, backlight=True):
        self.addr = addr
        self.bl = LCD_BL if backlight else 0x00
        self.bus = _SMBus(bus)
        self._init_display()

    # -- escrita crua de 1 byte no PCF8574 (sempre com backlight) -------------
    def _write_raw(self, data):
        self.bus.write_byte(self.addr, data | self.bl)
        time.sleep(0.0001)      # 100 us

    def _strobe(self, data):
        """Pulso em EN: o HD44780 lê o nibble na borda de descida de EN."""
        self._write_raw(data | LCD_EN)
        time.sleep(0.0005)      # 500 us com EN alto
        self._write_raw(data & ~LCD_EN)
        time.sleep(0.0001)

    def _send(self, value, mode):
        """Envia 1 byte em 2 nibbles (4 bits). mode: 0=comando, LCD_RS=dado."""
        self._strobe(mode | (value & 0xF0))            # nibble alto
        self._strobe(mode | ((value << 4) & 0xF0))     # nibble baixo

    def _init_display(self):
        # Sequencia canonica de inicializacao em modo 4 bits do HD44780.
        for cmd in (0x33, 0x32, 0x28, 0x0C, 0x06, LCD_CLEAR):
            #  0x33/0x32: entra em modo 4 bits;   0x28: 2 linhas, 5x8;
            #  0x0C: display on, cursor off;      0x06: entry mode (auto-inc);
            #  0x01: clear.
            self._send(cmd, 0)
        time.sleep(0.005)

    # -- API de alto nivel ----------------------------------------------------
    def clear(self):
        self._send(LCD_CLEAR, 0)
        time.sleep(0.002)

    def write_line(self, row, text):
        """Escreve na linha 0 ou 1, preenchendo com espacos ate 16 colunas
        (apaga sobras da mensagem anterior)."""
        self._send(0x80 | LINHA_OFFSET[row], 0)
        texto = (text or "")[:16]
        for ch in texto.ljust(16):
            self._send(ord(ch), LCD_RS)

    def show(self, linha0="", linha1=""):
        self.write_line(0, linha0)
        self.write_line(1, linha1)

    def backlight(self, on):
        self.bl = LCD_BL if on else 0x00
        self._write_raw(0x00)

    def close(self):
        try:
            self.clear()
            self.backlight(False)
        finally:
            self.bus.close()


def main():
    p = argparse.ArgumentParser(description="Teste isolado do LCD 16x2 I2C (HD44780/PCF8574).")
    p.add_argument("--addr", type=lambda x: int(x, 0), default=LCD_ADDR_PADRAO,
                   help="Endereco I2C do modulo (ex.: 0x27 ou 0x3F).")
    p.add_argument("--bus", type=int, default=I2C_BUS_PADRAO, help="Numero do barramento I2C.")
    p.add_argument("--linha0", default="Hello World", help="Texto da linha superior.")
    p.add_argument("--linha1", default="LCD I2C - Exp8", help="Texto da linha inferior.")
    args = p.parse_args()

    print(f"==== Teste de LCD I2C (Exp 8) - endereco {hex(args.addr)} @ i2c-{args.bus} ====")
    try:
        lcd = LcdI2c(addr=args.addr, bus=args.bus)
    except OSError as e:
        raise SystemExit(
            f"Falha no I2C ({e}). Verifique:\n"
            "  1) I2C habilitado:  sudo raspi-config -> Interface Options -> I2C\n"
            "  2) Modulo detectado: i2cdetect -y 1  (use o endereco mostrado em --addr)\n"
            "  3) Fiacao: VCC=5V, GND, SDA=GPIO2 (pino 3), SCL=GPIO3 (pino 5)"
        )
    try:
        lcd.show(args.linha0, args.linha1)
        print(f"  Escrito: '{args.linha0}' / '{args.linha1}'  (Ctrl+C para limpar e sair)")
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nInterrompido.")
    finally:
        lcd.close()


if __name__ == "__main__":
    main()
