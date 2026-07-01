# Experiência 6 — Desafio: Calculadora Binária Standalone

Versão **sem PC**: entrada por **teclado matricial 4×4** (GPIO) e saída em
**LCD 16×2 via I2C**. O Raspberry Pi 3 vira uma calculadora independente.

A arquitetura preserva o trabalho de Assembly: **o Python cuida só das bordas
de hardware** (ler o teclado, escrever no LCD) e **a aritmética é executada
pela ULA em Assembly ARM64** (`libalu.so`), chamada via `ctypes`.

```
Teclado 4x4 --(GPIO)--> [ Python: varredura ]
                                |
                                v
                        [ libalu.so : ULA em Assembly ARM64 ]   <- o "processador"
                                |
                                v
                        [ Python: formata ] --(I2C)--> LCD 16x2
```

## Arquivos

| Arquivo | Papel |
|---|---|
| `libalu.s` | ULA em Assembly ARM64 exposta como função `alu_calc(...)` |
| `keypad.py` | Varredura do teclado matricial 4×4 (GPIO) |
| `lcd_i2c.py` | Driver do LCD 16×2 (HD44780 via PCF8574 I2C) |
| `calculadora.py` | Cola: teclado → ULA (ctypes) → LCD |
| `Makefile` | Compila `libalu.so` |

---

## 1. Montagem física

**LCD I2C (4 fios):**

| LCD (backpack) | Pino físico do Pi | Função |
|---|---|---|
| VCC | pino 2 | 5V |
| GND | pino 6 | terra |
| SDA | pino 3 | GPIO2 / SDA1 |
| SCL | pino 5 | GPIO3 / SCL1 |

**Teclado matricial 4×4 (8 GPIOs):**

| Sinal | GPIO (BCM) | Pino físico |
|---|---|---|
| Linha 1–4 | 5, 6, 13, 19 | 29, 31, 33, 35 |
| Coluna 1–4 | 12, 16, 20, 21 | 32, 36, 38, 40 |

Sem resistores externos (usa pull-ups internos). Para mudar os pinos, edite
`ROWS`/`COLS` em `keypad.py`.

> ⚠️ O backpack I2C funciona em 5V e puxa SDA/SCL para 5V, enquanto o GPIO do Pi
> é 3,3V. Na prática costuma funcionar direto, mas o correto é um LCD/backpack
> de 3,3V ou um *level shifter*. Vale registrar no relatório.

## 2. Preparar o Raspberry (uma vez)

```bash
sudo raspi-config              # Interface Options -> I2C -> Enable  (e reinicie)
sudo apt install i2c-tools python3-smbus
pip install smbus2             # (recomendado; senao usa python3-smbus)
i2cdetect -y 1                 # anote o endereco do LCD (0x27 ou 0x3F)
```

Se o endereço não for `0x27`, edite `LCD_ADDR` no topo de `calculadora.py`.

GPIO em Python:
- Raspberry Pi OS **Bullseye**: `sudo apt install python3-rpi.gpio`
- Raspberry Pi OS **Bookworm**: `pip install rpi-lgpio` (substituto do RPi.GPIO)

## 3. Compilar a ULA e rodar

```bash
make                # gera libalu.so a partir do Assembly
python3 calculadora.py     # (ou: make run)
```

Se der erro de permissão de GPIO/I2C, rode com `sudo` ou confirme que seu
usuário está nos grupos `gpio` e `i2c`.

---

## 4. Como usar (mapa do teclado)

```
  Tecla  ->  função
   0, 1  ->  dígitos binários (até 4 bits: 0000..1111)
   A     ->  +        C  ->  *
   B     ->  -        D  ->  /
   *     ->  ! (fatorial)
   #     ->  = (calcular)
   2     ->  limpar / novo cálculo
```

**Fluxo:** digite A em binário → tecla da operação → digite B em binário →
`#` para calcular. Para fatorial: A → `*` → `#`.

No LCD:
- Linha 1: a expressão sendo montada (ex.: `1010 + 0101`).
- Linha 2: dicas e, ao final, o resultado (ex.: `=15 b1111`; divisão mostra
  `q=` quociente e `r=` resto). Erros: `div por 0`, `overflow`, `operacao`.

Depois do resultado, qualquer tecla volta ao início; `2` sempre reinicia.

---

## 5. Como isto atende ao enunciado do desafio

- **Sem periféricos de PC:** teclado matricial físico + LCD, o Pi não depende de
  teclado/monitor externos.
- **Barramento I2C:** o LCD usa só 2 fios de dados (SDA/SCL) em vez de 8+ em
  paralelo — exatamente o ponto do slide "Desacoplando do PC". O `lcd_i2c.py`
  escreve os bytes de controle do HD44780 na unha.
- **ULA em Assembly:** o cálculo continua sendo feito pelo código ARM64
  (`libalu.s`), agora como biblioteca — a camada de hardware é só a "casca".

## 6. Ideias de extensão

- Mostrar o **tempo de execução** (a `libalu.s` pode ler `cntvct_el0`; cabe
  numa segunda tela do LCD).
- Suportar mais de 4 bits, alternando telas para números grandes.
- Somar um **buzzer** de feedback a cada tecla.
