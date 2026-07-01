# Experiência 6 — Desafio: Calculadora Binária Standalone (C)

Versão **sem PC**: entrada por **teclado matricial 4×4** (GPIO) e saída em
**LCD 16×2 via I2C**. Feito em **C com wiringPi** (padrão dos tutoriais da
**Freenove Projects Board for Raspberry Pi**).

A aritmética continua no seu **Assembly ARM64**: a função `alu_calc()` está em
`libalu.s` e é **linkada** ao C. O C cuida só das bordas de hardware.

```
Teclado 4x4 --(GPIO)--> [ C/wiringPi: varredura ]
                                |
                                v
                    [ libalu.s : ULA em Assembly ARM64 ]   <- o "processador"
                                |
                                v
                [ C: formata ] --(I2C)--> LCD 16x2
```

## Arquivos

| Arquivo | Papel |
|---|---|
| `calculadora.c` | Teclado + LCD (wiringPi) + laço da calculadora |
| `libalu.s` | ULA em Assembly ARM64 (`alu_calc`), linkada ao C |
| `Makefile` | `gcc calculadora.c libalu.s -lwiringPi` |

---

## 1. Ligação física (Freenove board)

A Freenove board já traz os cabos/jumpers. Ligue conforme abaixo (e, se usar
outros pinos, ajuste `ROWS`/`COLS` e `LCD_ADDR` no topo do `calculadora.c`).

**LCD I2C (4 fios):**

| LCD | Pino físico do Pi | Função |
|---|---|---|
| VCC | pino 2 | 5V |
| GND | pino 6 | terra |
| SDA | pino 3 | GPIO2 / SDA1 |
| SCL | pino 5 | GPIO3 / SCL1 |

**Teclado matricial 4×4 (8 GPIOs, numeração BCM):**

| Sinal | GPIO (BCM) | Pino físico |
|---|---|---|
| Linha 1–4 | 5, 6, 13, 19 | 29, 31, 33, 35 |
| Coluna 1–4 | 12, 16, 20, 21 | 32, 36, 38, 40 |

Sem resistores externos (usa pull-ups internos). O I2C fica **sempre** em
GPIO2/GPIO3, independente da placa.

## 2. Preparar o Raspberry (uma vez)

```bash
sudo raspi-config              # Interface Options -> I2C -> Enable  (reinicie)
sudo apt install i2c-tools
i2cdetect -y 1                 # anote o endereco do LCD (0x27 ou 0x3F)
```

Se não for `0x27`, mude `#define LCD_ADDR` no `calculadora.c`.

**wiringPi** (biblioteca dos exemplos Freenove em C). Confira:
```bash
gpio -v          # se responder, ja esta instalado
```
Se não estiver, instale a versão mantida:
```bash
sudo apt install wiringpi        # tente primeiro
# se nao houver pacote, use o fork mantido:
#   https://github.com/WiringPi/WiringPi  (baixe o .deb e: sudo dpkg -i wiringpi_*.deb)
```

## 3. Compilar e rodar

```bash
make               # gera ./calculadora (C + Assembly + wiringPi)
sudo ./calculadora # wiringPi/GPIO costuma exigir root  (ou: make run)
```

---

## 4. Como usar (mapa do teclado)

```
  0, 1 -> dígitos binários (até 4 bits: 0000..1111)
  A -> +      C -> *        *  -> ! (fatorial)
  B -> -      D -> /        #  -> = (calcular)
                            2  -> limpar / novo cálculo
```

**Fluxo:** A em binário → tecla da operação → B em binário → `#`.
Fatorial: A → `*` → `#`.

No LCD: linha 1 mostra a expressão (`1010 + 0101`); linha 2 mostra o resultado
(`=15 b1111`; divisão mostra `q=` quociente e `r=` resto). Erros aparecem como
`div por 0`, `overflow`, `operacao`. Depois do resultado, qualquer tecla volta
ao início; `2` sempre reinicia.

---

## 5. Como isto atende ao enunciado do desafio

- **Sem periféricos de PC:** teclado matricial + LCD; o Pi não depende de
  teclado/monitor externos.
- **Barramento I2C:** o LCD usa só 2 fios de dados (SDA/SCL) em vez de 8+ em
  paralelo — o ponto do slide "Desacoplando do PC". O driver do HD44780 escreve
  os bytes de controle na unha (`lcd_send`), via `wiringPiI2CWrite`.
- **ULA em Assembly:** o cálculo é feito pelo código ARM64 (`libalu.s`), agora
  linkado ao C — a camada de hardware é só a "casca".

## 6. Trocar a ULA de Assembly por C (se quiser)

Se preferir dispensar o Assembly, dá para substituir a chamada `alu_calc(...)`
por uma função C equivalente (a lógica está no `calculadora.c` da pasta de cima).
Basta remover `libalu.s` do `Makefile` e implementar `alu_calc` em C. Me avise
que eu faço.
