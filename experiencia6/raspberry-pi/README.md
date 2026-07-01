# Experiência 6 — Arquiteturas em Duelo (lado ARM / Raspberry Pi 3)

Calculadora binária em **Assembly ARM64 (AArch64)** rodando no **Raspberry Pi 3
(Cortex-A53)** — o lado *ARM* do duelo ARM vs RISC-V (ESP32).

Lê dois operandos em **binário de 4 bits (valores de 0 a 15, `0000` a `1111`)**
pelo teclado, executa a operação e mostra o resultado em **decimal e binário**
no monitor (HDMI/VGA), junto do **tempo de execução** medido pelo contador de
ciclos do próprio ARM. Entradas fora da faixa são rejeitadas com aviso, sem
derrubar o programa (requisito de estabilidade de erro — RNF01).

> Apenas as **entradas** são limitadas a 4 bits. O **resultado** usa a largura
> necessária (ex.: `1111 * 1111 = 225`, `0101! = 120`).

| Operação | Símbolo | Observação |
|----------|:-------:|------------|
| Soma            | `+` | `ADD` direto do pipeline |
| Subtração       | `-` | pode resultar negativo |
| Multiplicação   | `*` | `MUL` |
| Divisão inteira | `/` | mostra quociente e resto; **trata divisão por zero** |
| Fatorial        | `!` | iterativo, **detecta overflow de 64 bits** |

## Arquivos

- `calculadora.s` — implementação principal em Assembly AArch64 (usa syscalls do Linux, sem libc).
- `calculadora.c` — versão de referência em C (para conferir resultados / rodar em SO 32 bits).
- `Makefile` — build com `as` + `ld`.

---

## ⚠️ Importante: NÃO é Arduino IDE

Diferente das experiências 1–5 (ESP32), o **Raspberry Pi 3 não é um
microcontrolador** — é um **computador Linux completo**. Você **não usa o
Arduino IDE** nem grava firmware por USB.

Você escreve, compila e roda o código **dentro do próprio Pi** (que já tem
Linux, montador `as`, `gcc`, etc.). Há três formas de acessar o Pi:

### Opção A — Direto na bancada (é o cenário da experiência)
Conecte **teclado USB + monitor por HDMI/VGA** no Raspberry Pi e use-o como um
PC normal. Abra o terminal e siga para "Compilar e rodar".
> É exatamente o que o enunciado descreve: *"usar o teclado do PC da bancada"* e
> *"monitor do laboratório via HDMI-VGA"*.

### Opção B — SSH pela rede (do seu PC)
Com o Pi ligado na mesma rede:
```bash
ssh pi@<IP-do-raspberry>      # ex.: ssh pi@192.168.0.42
# senha padrão antiga: raspberry (se não foi trocada)
```
Descubra o IP no próprio Pi com `hostname -I`, ou tente `ssh pi@raspberrypi.local`.
No Windows você pode usar o **PowerShell** (`ssh` já vem incluso) ou o PuTTY.

### Opção C — VNC
Acesso à área de trabalho gráfica remota (habilite com `sudo raspi-config` →
*Interface Options* → *VNC*). Útil, mas para esta experiência o terminal basta.

---

## Pré-requisito: SO de 64 bits

O `calculadora.s` é **AArch64 (64 bits)**. Confirme no Pi:
```bash
uname -m
```
- `aarch64` → tudo certo, siga em frente.
- `armv7l` → você está no **Raspberry Pi OS de 32 bits**. O Assembly 64 bits não
  vai montar. Use a versão em C (`make c`) **ou** reinstale o Raspberry Pi OS
  *64-bit*. (Se precisar mesmo do Assembly 32 bits/AArch32, me avise que eu gero.)

---

## Compilar e rodar

No diretório `experiencia6/raspberry-pi/`, dentro do Pi:

```bash
make            # monta com as + ld -> gera ./calculadora
./calculadora   # (ou: make run)
```

Versão em C de referência (opcional, serve para conferir / rodar em 32 bits):
```bash
make c          # gera ./calculadora_c (gcc)
./calculadora_c
```

Limpar artefatos: `make clean`

---

## Exemplo de uso

```
==== Calculadora Binaria ARM (AArch64) - Exp 6 ====
Operacoes: + - * /  e  ! (fatorial)

Operando A (binario, 4 bits 0..15): 1010
Operacao (+ - * / !): +
Operando B (binario, 4 bits 0..15): 0101
Resultado: 15  (binario: 1111)
Tempo: 4000000 ns  (1000000 repeticoes)  =>  4 ns/operacao  [cntvct_el0]

Operando A (binario, 4 bits 0..15): 10000
ERRO: entrada deve ter 4 bits (0 a 15, ex.: 0000 a 1111). Tente novamente.

Operando A (binario, 4 bits 0..15): 1111
Operacao (+ - * / !): /
Operando B (binario, 4 bits 0..15): 0000
ERRO: divisao por zero (operacao invalida). Tente novamente.

Operando A (binario, 4 bits 0..15): 0101
Operacao (+ - * / !): !
Resultado: 120  (binario: 1111000)
Tempo: 21000000 ns  (1000000 repeticoes)  =>  21 ns/operacao  [cntvct_el0]

Continuar? (s/n): n
```

> Os valores de tempo acima são **ilustrativos** — dependem do clock do seu Pi.
> Erros (faixa, divisão por zero, overflow) não são medidos.

Valores de conferência (entradas de 0 a 15): `1010-1111 = -5`; `0110*0111 = 42`;
`1111/0100` → quociente `3`, resto `3`; `1111! (15!) = 1307674368000`. Entradas
como `10000` (16) são rejeitadas por passarem de 4 bits.

> O resultado negativo (ex.: `-5`) é mostrado em **sinal-módulo** no campo
> binário (`-101`) para facilitar a leitura. Internamente o ARM opera em
> complemento de dois nos registradores de 64 bits.

---

## Como o tempo é medido

Uma operação isolada (`add`, `mul`, ...) leva **poucos nanossegundos** — bem
menos que a resolução do contador de tempo do Pi (~52 ns/tick a 19,2 MHz). Se
medíssemos uma única operação, o resultado seria quase sempre `0`. Por isso a
operação é executada **`REPS = 1 000 000` vezes** e reportamos:

- **tempo total** do lote de repetições;
- **tempo por operação** = total ÷ `REPS`.

| | Assembly (`calculadora.s`) | C (`calculadora.c`) |
|---|---|---|
| Fonte de tempo | `cntvct_el0` (contador virtual do ARM, lido por `mrs`) | `clock_gettime(CLOCK_MONOTONIC)` |
| Conversão p/ ns | `× 1e9 / cntfrq_el0` | direto (`tv_sec`/`tv_nsec`) |

O uso do `cntvct_el0` no Assembly é proposital: é um **registrador de sistema da
arquitetura ARM**, análogo ao CSR `time`/`cycle` do RISC-V — ou seja, os dois
lados do duelo medem tempo com o mesmo tipo de recurso de hardware. Para mudar o
número de repetições, altere `REPS` (`.equ REPS` no `.s`; `#define REPS` no `.c`).

> Como os operandos são fixos numa rodada, no `.s` o laço genuinamente repete a
> instrução; no `.c` os operandos e o *sink* são `volatile` para impedir que o
> `-O2` elimine ou "ice" o laço.

---

## Por que ARM 64 bits importa aqui (escalabilidade N-bits)

O enunciado pede comparar a operação em **N bits (de 4 até 64)**. O ponto do
duelo:

- **Raspberry Pi 3 (ARM Cortex-A53, 64 bits):** registradores de 64 bits operam
  inteiros grandes em um único ciclo. Ótima escalabilidade.
- **ESP32 (RISC-V, 32 bits):** números que excedem 32 bits exigem **instruções
  encadeadas** (somar partes baixas + *carry* + partes altas), gerando *overhead*
  de ciclos.

A entrada é de **4 bits (0–15)**, o mínimo da bancada — com isso o maior
fatorial é `15! = 1307674368000`, que cabe folgado num registrador de 64 bits.
O **monitor de overflow** do `!` fica como proteção para a generalização em N
bits (`20!` ainda cabe em 64 bits, `21!` estoura) — daí a faixa "4 a 64 bits"
usada na comparação do relatório.

---

## Mapeamento com o fluxo da ULA (enunciado)

1. **Interrupção do teclado** → aqui via `read` (polling de `stdin`).
2. **Decodificador de OpCode** → compara o caractere da operação (`+ - * / !`).
3. **ADD / SUB / MUL / FAT / DIV** → instruções `add`, `sub`, `mul`, `sdiv`/`msub`, laço de fatorial.
4. **Conversão Binário → ASCII** → rotinas `print_dec` / `print_bin`.
5. **Buffer de vídeo (HDMI-VGA)** → `write` para `stdout` (terminal no monitor).

## Próximos passos (opcional)

- **Lado RISC-V do duelo:** implementar a mesma calculadora no ESP32 (baremetal)
  em `experiencia6/esp32/` e medir a diferença em N bits.
- **Desafio avançado (standalone):** trocar o teclado do PC por **teclado
  matricial via GPIO** e a saída por **display LCD via I2C**, desacoplando o Pi
  do PC da bancada.
