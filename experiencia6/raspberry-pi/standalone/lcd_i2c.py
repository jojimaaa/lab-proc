"""
lcd_i2c.py - Driver de LCD 16x2 (HD44780) via backpack I2C (PCF8574).

Fala com o LCD em modo 4 bits atraves do expansor PCF8574. Mapeamento de bits
tipico dos modulos "LCD1602 I2C":
    bit0 = RS   bit1 = RW   bit2 = EN   bit3 = backlight   bits4-7 = D4..D7

Endereco I2C: normalmente 0x27 ou 0x3F. Descubra com:  i2cdetect -y 1
"""
import time

try:
    from smbus2 import SMBus
except ImportError:
    try:
        from smbus import SMBus
    except ImportError:
        raise SystemExit(
            "Biblioteca I2C nao encontrada.\n"
            "  pip install smbus2   (ou: sudo apt install python3-smbus)"
        )

RS = 0x01           # Register Select (0 = comando, 1 = dado)
EN = 0x04           # Enable
BACKLIGHT = 0x08    # luz de fundo ligada


class LcdI2C:
    def __init__(self, addr=0x27, bus_id=1, cols=16, rows=2):
        self.addr = addr
        self.cols = cols
        self.bus = SMBus(bus_id)
        self.backlight = BACKLIGHT
        # sequencia de inicializacao do HD44780 em modo 4 bits
        for cmd in (0x33, 0x32, 0x28, 0x0C, 0x06, 0x01):
            self._send(cmd, 0)
        time.sleep(0.005)

    # ---- baixo nivel ----
    def _write(self, data):
        self.bus.write_byte(self.addr, data | self.backlight)
        time.sleep(0.0001)

    def _strobe(self, data):
        self._write(data | EN)
        time.sleep(0.0005)
        self._write(data & ~EN)
        time.sleep(0.0001)

    def _send(self, value, mode):
        """Envia 1 byte em dois nibbles. mode = 0 (comando) ou RS (dado)."""
        self._strobe(mode | (value & 0xF0))
        self._strobe(mode | ((value << 4) & 0xF0))

    # ---- alto nivel ----
    def clear(self):
        self._send(0x01, 0)
        time.sleep(0.002)

    def set_cursor(self, col, row):
        offsets = [0x00, 0x40, 0x14, 0x54]
        self._send(0x80 | (offsets[row] + col), 0)

    def write(self, text, row=0, col=0):
        self.set_cursor(col, row)
        for ch in text:
            self._send(ord(ch), RS)
