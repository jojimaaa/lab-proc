# Experiência 7 — Metrônomo: Temporização e PWM no Raspberry Pi 3

Metrônomo em **Python** rodando no **Raspberry Pi 3 (Cortex-A53)**, usando
`RPi.GPIO`. Bate um pulso mecânico (servo), luminoso (LED) e sonoro (buzzer) a
cada intervalo, com o **andamento (BPM) ajustável em tempo real por dois
botões** e **temporização corrigida contra drift**.

> Como na Experiência 6, o RPi3 **não é um microcontrolador** — é um computador
> Linux. Você escreve, compila (aqui só interpreta) e roda **dentro do próprio
> Pi**. Não há Arduino IDE.

---

## Requisitos atendidos (matriz de testes do enunciado)

| ID | Requisito | Como é atendido no código |
|----|-----------|---------------------------|
| **RF01** | Temporização 1 Hz (jitter < 5 ms) | Agenda **absoluta** com `time.perf_counter()`: `proximo += periodo` a cada batida, em vez de `sleep(periodo)` puro — elimina o acúmulo de erro. |
| **RF02** | Controle de BPM dinâmico | Dois botões disparam callbacks que só atualizam a variável global `_bpm` (protegida por `Lock`). O laço sonoro **não é interrompido**. |
| **RF03** | Modulação PWM | Servo alterna entre 5% e 10% de duty (0°↔180°, varredura pendular); LED faz **rampa de brilho** (100%→0%) via PWM a 1 kHz preenchendo o intervalo. |
| **RNF01** | Debouncing físico | `GPIO.add_event_detect(pino, GPIO.FALLING, callback=..., bouncetime=200)` — ignora reativações por 200 ms após o gatilho. |

---

## Fiação (numeração BCM)

| Componente | GPIO (BCM) | Pino físico | Observação |
|------------|:----------:|:-----------:|------------|
| Botão **+BPM** | GPIO17 | 11 | Outro terminal no **GND**. Pull-up interno → borda de descida. |
| Botão **−BPM** | GPIO27 | 13 | Idem. |
| **LED** de status | GPIO18 | 12 | Em série com **resistor de 330 Ω** para o GND. |
| **Servo SG90** (sinal) | GPIO12 | 32 | `+5V` e `GND` do servo na alimentação do Pi. |
| **Buzzer** (sinal) | GPIO22 | 15 | Outro terminal no GND (buzzer **ativo**, on/off digital). |

> **Botões:** o código usa `PUD_UP` (pull-up interno) e detecta `GPIO.FALLING`.
> Ligue cada botão entre o GPIO e o **GND** — ao pressionar, o pino vai de
> 3,3 V para 0 V (borda de descida). Se preferir os resistores externos de
> pull-down do diagrama, troque para `PUD_DOWN` + `GPIO.RISING`.

> **Servo:** o SG90 pode puxar corrente demais do Pi em movimento; o ideal é
> alimentá-lo por uma **fonte 5 V externa** com o **GND comum** ao do Pi.

---

## Pré-requisitos

```bash
sudo apt update && sudo apt install -y python3-rpi.gpio   # normalmente já vem
# ou:  pip install RPi.GPIO
```

Confirme que está num Raspberry Pi (o import de `RPi.GPIO` falha em PC comum).

---

## Rodar

No diretório `experiencia7/raspberry-pi/`, dentro do Pi:

```bash
python3 metronomo.py                 # 60 BPM (1 Hz), buzzer ligado
python3 metronomo.py --bpm 90        # começa em 90 BPM
python3 metronomo.py --no-buzzer     # sinal sonoro desligado (configurável)
# atalhos equivalentes com make:
make run
make run-silencioso
```

`Ctrl+C` encerra e libera os GPIOs (`GPIO.cleanup()`).

Exemplo de saída ao pressionar os botões:

```
==== Metronomo PWM (Exp 7) - PCS3732 ====
BPM inicial: 60  |  buzzer: ligado
Botoes: GPIO17 = +5 BPM   GPIO27 = -5 BPM
Ctrl+C para sair.

> BPM alterado para 65
> BPM alterado para 70
> BPM alterado para 65
```

---

## Decisões de projeto (o "porquê")

- **Correção de drift.** `time.sleep(1)` sozinho acumula o tempo de execução do
  laço a cada iteração e o metrônomo atrasa progressivamente. Usamos uma
  **agenda absoluta** (`proximo += periodo`): o alvo da próxima batida não
  depende de quanto durou a batida atual, então o erro **não acumula**. É a
  versão robusta do `sleep(1.0 - drift_time)` citado no enunciado.

- **Multiplexação por threads.** A escuta dos botões roda na **thread de eventos
  do `RPi.GPIO`** (callbacks) e só escreve `_bpm`. O **laço crítico de 1 Hz**
  fica na thread principal e nunca bloqueia esperando o hardware — aproveitando
  o multiprocessamento nativo do ARM Cortex-A53 (4 núcleos).

- **PWM por software (`RPi.GPIO`).** Simples e suficiente para o laboratório.
  Para um servo **sem tremor** (jitter), o ideal é **PWM por hardware** (canais
  dedicados nas GPIOs 12/13/18/19) via `pigpio`. Posso gerar essa variante se
  precisar da precisão do RF01/RF03 num osciloscópio.

- **LED em rampa dentro do intervalo.** A rampa de brilho preenche exatamente o
  tempo entre batidas, então ela dá o efeito visual do RF03 **sem** roubar
  precisão do RF01.

---

## Limitações do RPi3 para tempo real (discutidas no enunciado)

- Raspbian padrão **não é RTOS**: há *jitter* do escalonador. Para prazos
  estritos usaria patch `PREEMPT_RT` ou bare-metal.
- **Sem RTC** interno: perde a hora ao reiniciar (mitigável com DS3231 via I²C).
- Perda de energia descarta o BPM atual (guardado só em RAM): dá para persistir
  em arquivo/SD periodicamente.
