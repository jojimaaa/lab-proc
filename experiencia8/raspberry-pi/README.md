# Experiência 8 — Fechadura Eletrônica no Raspberry Pi 3

Fechadura eletrônica em **Python** rodando no **Raspberry Pi 3 (Cortex-A53)**.
Entrada de **senha por teclado matricial 4×4**, status em **LCD 16×2 via I²C**,
**feedback sonoro** por buzzer e **verificação da integridade física** por um
sensor (reed switch/microchave ou ultrassônico). O ferrolho é movido por um
**servomotor**. Tudo sob uma **máquina de estados não-bloqueante**.

> Como nas Experiências 6 e 7, o RPi3 **não é um microcontrolador** — é um
> computador Linux. Você escreve, roda e depura **dentro do próprio Pi**. Não há
> Arduino IDE.

---

## Estrutura dos arquivos

O enunciado pede primeiro **cada componente isolado** e só depois a **integração**.

| Arquivo | Papel | Item do enunciado |
|---------|-------|-------------------|
| [`keypad.py`](keypad.py) | Teclado matricial 4×4 (varredura + debounce, não-bloqueante) | Entrada de senha (RF01) |
| [`lcd_i2c.py`](lcd_i2c.py) | LCD 16×2 HD44780 via PCF8574 (I²C) | Display de status (RF02) |
| [`buzzer.py`](buzzer.py) | Buzzer com padrões sonoros **não-bloqueantes** | Feedback sonoro (RF04) |
| [`sensor.py`](sensor.py) | Sensor de tranca (digital ou ultrassônico) | Integridade física (RF03) |
| [`trava.py`](trava.py) | Atuador do ferrolho (servo/relé) | Acionamento (RF05) |
| [`fechadura.py`](fechadura.py) | **Integração**: máquina de estados da fechadura | Fluxo de estados + segurança |
| [`RELATORIO.md`](RELATORIO.md) | Relatório: requisitos, arquitetura, planos, Q&A e segurança (ABNT) | Documentação completa |

Rode cada teste isolado **antes** de integrar (é a base do plano de depuração —
a *Regra de Ouro*: nunca integre o que não passou no teste unitário):

```bash
make test-keypad     # teclado (inclui diagnóstico de repouso das colunas)
make test-lcd        # LCD I2C (escreve "Hello World")
make test-buzzer     # buzzer (sucesso / erro / alerta)
make test-sensor     # sensor de tranca
make test-trava      # atuador (servo)
make run             # fechadura integrada
```

---

## Requisitos atendidos (matriz de testes do enunciado)

| ID | Requisito | Como é atendido no código |
|----|-----------|---------------------------|
| **RF01** | Entrada de senha numérica | `keypad.py` varre a matriz 4×4 e emite 1 evento por tecla; `fechadura.py` monta 4–6 dígitos (`*`=apagar, `#`=submeter, `D`=cancelar). |
| **RF02** | LCD em tempo real | `lcd_i2c.py` (HD44780/PCF8574); a tela é reescrita **na transição** de estado, só quando muda (latência < 200 ms). |
| **RF03** | Integridade física | `sensor.py` lê o estado; a FSM vai a **ALARME** se estiver logicamente trancada mas o sensor acusar porta aberta. |
| **RF04** | Feedback sonoro | `buzzer.py`: sucesso (2 bipes curtos), erro (bipe longo), alerta (sirene). |
| **RF05** | Acionamento da tranca | `trava.py` (servo) abre ao validar e re-tranca após *timeout*. |
| **RNF01** | Recuperação de erros | 3 erros → **cooldown** de 15 s **sem travar** o processo. |
| **RNF02** | Não-bloqueio | Laço cooperativo; buzzer por `tick()` — teclado e sensor nunca congelam. |
| **RNF03** | Segurança da senha | PBKDF2-HMAC-SHA256 + sal (`hashlib`); comparação em tempo constante (`hmac.compare_digest`). |
| **RNF04** | Debouncing | Evento único por pressão (janela ~40 ms). |

---

## Fiação (numeração BCM)

Placa: **Freenove Projects Board**. Ajuste os pinos no topo de cada módulo se a
sua montagem diferir.

| Componente | GPIO (BCM) | Observação |
|------------|:----------:|------------|
| Teclado — **linhas** | 16, 20, 21, 26 | Saídas de varredura |
| Teclado — **colunas** | 19, 13, 6, 5 | Entradas com *pull-down* |
| **LCD** SDA | GPIO2 (pino 3) | I²C (fixo) |
| **LCD** SCL | GPIO3 (pino 5) | I²C (fixo). VCC=5V, GND. |
| **Buzzer** | GPIO12 | Buzzer **ativo**, on/off digital |
| **Tranca** (servo) | GPIO18 | `+5V`/`GND` do servo, de preferência em fonte externa |
| **Sensor** digital | GPIO17 | reed/microchave entre GPIO e GND (*pull-up* interno) |
| **Sensor** ultrassônico | TRIG 23 / ECHO 24 | HC-SR04 — **ECHO precisa de divisor de tensão** |

> **Teclado (pull-down):** o código usa varredura ativo-alto (igual à Exp 6).
> GPIO13/19 já nascem em *pull-down*, mas **GPIO5/6 nascem em *pull-up***. Se o
> teclado "printar sozinho", fixe no `/boot/firmware/config.txt` e reinicie:
> ```
> gpio=5,6,13,19=ip,pd
> ```
> Confira com `pinctrl get 5,6,13,19` (devem mostrar `pd`). Diagnóstico:
> `make test-keypad` mostra as colunas em repouso — todas devem ler `0`.

> **LCD:** o endereço I²C típico é `0x27` (PCF8574) ou `0x3F` (PCF8574A).
> Descubra o seu com `make i2c` (`i2cdetect -y 1`) e passe em `--lcd-addr`.

> **Sensor:** o padrão é **digital** (reed switch/microchave) — o mais simples
> para "trancada × aberta" e o que casa com a análise de segurança do relatório
> (ataque por ímã). Use `--sensor-tipo ultrassonico` para o HC-SR04.

> **ECHO do HC-SR04 é 5V:** nunca ligue direto num GPIO de 3,3V. Use um divisor
> resistivo (ex.: 1 kΩ + 2 kΩ) do ECHO para o GPIO24.

---

## Pré-requisitos (uma vez)

```bash
sudo raspi-config                 # Interface Options -> I2C -> Enable (reinicie)
make install                      # RPi.GPIO + smbus + i2c-tools
make i2c                          # confirma o endereço do LCD
```

Para o servo sem tremor (opcional): `sudo apt install pigpio python3-pigpio && sudo systemctl enable --now pigpiod`.

---

## Rodar

No diretório `experiencia8/raspberry-pi/`, dentro do Pi:

```bash
python3 fechadura.py                      # PIN padrão 2468, servo + sensor digital + LCD
python3 fechadura.py --pin 1357           # troca o PIN inicial
python3 fechadura.py --sensor-tipo ultrassonico
python3 fechadura.py --trava-tipo rele --trava-pino 18
python3 fechadura.py --lcd-addr 0x3F
python3 fechadura.py --sem-lcd            # sem LCD: status espelhado no console
```

`Ctrl+C` encerra, re-tranca e libera os GPIOs (`GPIO.cleanup()`).

### Teclado (mapa)

```
  0-9  -> dígitos da senha (4 a 6)
  #    -> submeter (Enter)
  *    -> apagar o último dígito (backspace)
  D    -> cancelar / limpar
```

### Segurança da senha (modo produção)

O dispositivo guarda **apenas o hash** (`sal$hash`), nunca o texto plano. Gere o
hash **offline** e implante só ele:

```bash
make gerar-hash PIN=2468          # imprime "sal_hex$hash_hex"
python3 fechadura.py --hash "<sal$hash>"   # o PIN em texto nunca toca o Pi
```

---

## Decisões de projeto (o "porquê")

- **Máquina de estados não-bloqueante.** O maior risco de integração apontado no
  enunciado é o *código bloqueante*: um `sleep()` no buzzer congelaria a
  varredura do teclado e "cegaria" o sensor. Por isso o laço é **cooperativo**:
  lê teclado e sensor a cada iteração e agenda o som por `tick()`. As únicas
  esperas são os movimentos discretos do servo, fora do laço de monitoramento.

- **I²C para o LCD.** Um LCD paralelo exigiria 6+ GPIOs; o backpack PCF8574 usa
  **2 fios** (SDA/SCL), liberando pinos para teclado/buzzer/sensor/servo.

- **Senha como hash (PBKDF2 + sal).** Nunca em texto plano. SHA-256 puro é rápido
  demais para senhas; usa-se PBKDF2 (KDF lenta), com comparação em **tempo
  constante** (`hmac.compare_digest`) contra *timing attacks*. Ver RELATORIO §7.

- **Sensor reed como caso de estudo.** É deliberadamente vulnerável a ímã
  externo — o vetor de ataque analisado no relatório (tampering + spoofing).

---

## Limitações (discutidas no relatório)

- Raspbian **não é RTOS**: há *jitter* do escalonador — irrelevante para os
  prazos *soft real-time* desta fechadura, mas relevante como superfície de
  *timing attack* (daí a comparação em tempo constante).
- O **servo** puxa corrente: use fonte 5 V externa com GND comum, senão o Pi
  pode reiniciar ao mover o ferrolho.
- **Bug de *clock stretching*** do I²C do BCM283x pode corromper telas com fios
  longos ou escravos exigentes; encurte os fios / reduza a *baudrate* se ocorrer.
