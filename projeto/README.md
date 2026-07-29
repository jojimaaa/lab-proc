# Tradutor Embarcado de LIBRAS

Implementação do projeto final de **PCS3724 — Sistemas Embarcados** (Escola
Politécnica da USP), conforme o documento de arquitetura: um sistema
embarcado que captura gestos manuais em tempo real com uma webcam, extrai o
esqueleto da mão (21 landmarks, MediaPipe Hands), classifica a letra do
alfabeto em LIBRAS, monta letras em palavras com suavização temporal e
apresenta o resultado em **texto** (frontend web) e **voz** (TTS) — tudo
processado localmente (computação de borda), sem nuvem.

```
webcam ──► captura ──► pré-processamento ──► landmarks ──► classificador ──► lógica temporal ──┐
 (USB)     (OpenCV)     (resize + BGR→RGB)   (MediaPipe)      (k-NN)        (votação + palavras) │
                                                                                                 ▼
           monitor de desempenho ─────────────► servidor de aplicação (Flask) ──► frontend web (HDMI)
           (CPU, RAM, clock, temp, CPI)                                      └──► síntese de voz (TTS)
```

Cada bloco do diagrama de blocos da arquitetura corresponde a um módulo
Python independente e testável (estilo dutos e filtros).

---

## Estrutura do projeto

```
projeto/
├── libras/                  # pacote principal (um módulo por bloco da arquitetura)
│   ├── config.py            # configuração central (câmera, limiares, servidor…)
│   ├── capture.py           # bloco 1 — captura (webcam real ou fonte sintética)
│   ├── preprocess.py        # bloco 2 — redimensiona e converte BGR→RGB
│   ├── landmarks.py         # bloco 3 — MediaPipe Hands (+ extratores de teste)
│   ├── features.py          # normalização geométrica dos 21 landmarks
│   ├── classifier.py        # bloco 4 — classificador k-NN + dataset CSV
│   ├── temporal.py          # bloco 5 — votação em janela + montagem de palavras
│   ├── server.py            # bloco 6 — servidor Flask (frontend + APIs + MJPEG)
│   ├── tts.py               # bloco 7 — síntese de voz (pyttsx3/espeak/nulo)
│   ├── monitor.py           # módulo transversal — métricas do processador
│   ├── pipeline.py          # orquestração dos estágios + estado compartilhado
│   ├── demo.py              # modo demonstração (gestos sintéticos, sem hardware)
│   ├── main.py              # ponto de entrada:  python -m libras.main
│   ├── collect.py           # coleta de amostras: python -m libras.collect
│   ├── import_images.py     # dataset a partir de imagens prontas (sem saber LIBRAS)
│   ├── get_model.py         # baixa o modelo da API nova do MediaPipe
│   └── benchmark.py         # benchmark:         python -m libras.benchmark
├── frontend/                # página servida ao monitor (vídeo, tradução, dashboard)
├── tests/                   # testes unitários de requisitos (ver tabela abaixo)
├── data/                    # dataset de gestos coletados (dataset.csv)
├── requirements.txt         # dependências completas (dispositivo alvo)
└── requirements-dev.txt     # dependências mínimas (demo, testes, benchmark)
```

---

## Instalação

### Em qualquer máquina (desenvolvimento — sem webcam)

Requer apenas **Python ≥ 3.9**. O modo demo, os testes e o benchmark não
usam OpenCV/MediaPipe:

```bash
cd projeto
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements-dev.txt
```

### No dispositivo alvo (Raspberry Pi com webcam)

No Pi a versão do Python **importa**, e o intervalo é estreito. Requisitos:

- **Raspberry Pi OS 64-bit** (`uname -m` = `aarch64`; para 32-bit/`armv7l` não
  há wheel no PyPI);
- **Python 3.9 a 3.12** — a última versão do MediaPipe com wheel `aarch64` é a
  **0.10.18**, e ela só publica tags `cp39`–`cp312`;
- **MediaPipe < 1.0** — as wheels `aarch64` da 1.x são compiladas com a
  extensão criptográfica ARMv8 (AES), ausente no Pi 4/5, e o import aborta com
  `Illegal instruction` (veja Solução de problemas). A 1.0.0 é `py3-none`, ou
  seja, instala em qualquer Python 3 — inclusive onde vai quebrar.

No Raspberry Pi OS **Bookworm** o Python padrão é 3.11 e serve direto:

```bash
sudo apt update
sudo apt install python3-opencv espeak-ng   # OpenCV do sistema + TTS leve
cd projeto
python3 -m venv --system-site-packages .venv   # reaproveita o cv2 do apt
source .venv/bin/activate
pip install numpy flask psutil "mediapipe>=0.10.9,<1.0" pyttsx3 pytest
```

No **Trixie** (ou qualquer imagem com Python 3.13+) o comando acima falha com
`No matching distribution found for mediapipe`: não existe wheel `aarch64` de
0.10.x para `cp313`. Traga um Python 3.12 próprio — o `uv` baixa um build
pronto, sem compilar:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
sudo apt install espeak-ng
cd projeto
uv venv -p 3.12 .venv
source .venv/bin/activate
uv pip install numpy flask psutil "mediapipe==0.10.18" opencv-python pyttsx3 pytest
```

> Com um Python próprio o truque do `--system-site-packages` não vale: o `cv2`
> do apt pertence ao Python do sistema. Por isso a linha acima instala
> `opencv-python` (há wheel `aarch64`) em vez de reaproveitar o do apt.

Para o CPI/IPC aparecerem no dashboard e no benchmark (opcional):

```bash
sudo apt install linux-perf
# permite `perf stat -a` (medição de todo o sistema) sem root:
sudo sysctl kernel.perf_event_paranoid=0
# para persistir após reiniciar:
echo "kernel.perf_event_paranoid=0" | sudo tee /etc/sysctl.d/99-perf.conf
```

---

## Como rodar

### 1. Modo demonstração (nenhum hardware necessário)

Soletra um texto com gestos sintéticos que percorrem **todo** o pipeline
real (classificação, votação temporal, palavras, dashboard, TTS):

```bash
python -m libras.main --demo
```

Abra **http://localhost:8001/** no navegador: o painel de tradução mostra as
letras sendo confirmadas e as palavras "LIBRAS" e "USP" se formando; o
dashboard mostra as métricas do processador ao vivo.

Opções úteis:

```bash
python -m libras.main --demo --demo-text "OLA MUNDO"   # outro texto
python -m libras.main --demo --no-tts --port 8080      # sem voz, outra porta
```

> **MediaPipe 0.10.31 ou mais novo?** Essas versões removeram a API legada
> (`mp.solutions`) — o erro típico é
> `AttributeError: module 'mediapipe' has no attribute 'solutions'`.
> O projeto suporta as duas APIs automaticamente; para a nova, baixe o
> modelo uma única vez (~8 MB, depois tudo segue offline):
>
> ```bash
> python -m libras.get_model
> ```

### 2a. Não sabe LIBRAS? Use um dataset pronto de imagens

Não é preciso saber os gestos para treinar o classificador: dá para usar um
banco público de **imagens do alfabeto em LIBRAS** e convertê-lo em amostras
de landmarks com o importador do projeto:

1. Baixe um dataset (opções conhecidas):
   - [Brazilian Sign Language Alphabet Dataset](https://github.com/biankatpas/Brazilian-Sign-Language-Alphabet-Dataset)
     — 4.411 imagens, 15 letras estáticas (A, B, C, D, E, I, L, M, N, O, R,
     S, U, V, W), 200×200 px com fundo homogêneo;
   - [Alfabeto em LIBRAS (Roboflow)](https://universe.roboflow.com/elainesilva/alfabeto-em-libras-qrvnw)
     — 1.735 imagens anotadas;
   - [LIBRAS (Kaggle)](https://www.kaggle.com/datasets/williansoliveira/libras)
     — imagens do alfabeto.
2. Organize (se já não estiver assim) uma subpasta por letra:
   `imagens/A/*.jpg`, `imagens/B/*.jpg`…
3. Importe — o MediaPipe extrai os landmarks de cada imagem e alimenta o
   mesmo `data/dataset.csv` da coleta por webcam:

```bash
python -m libras.import_images caminho/para/imagens --limite 200
```

Observações: exige OpenCV + MediaPipe instalados (como a coleta); imagens em
que nenhuma mão é detectada são ignoradas e contabilizadas no resumo; os
datasets públicos cobrem só as letras **estáticas** do alfabeto (as letras
com movimento, como H, J, K, X, Y e Z, ficam fora do reconhecimento estático
de qualquer forma).

Por padrão cada imagem gera 3 variações extras com jitter nos landmarks
(`--augment 3`), simulando o ruído de detecção da webcam ao vivo — isso
melhora bastante a taxa de confirmação. Se o estágio de classificação ficar
lento demais na Raspberry Pi (veja a latência no dashboard), reduza o
dataset com `--augment 2` ou `--limite 100`.

### 2b. Coletar amostras de gestos (dispositivo com webcam + MediaPipe)

O classificador aprende com **suas** amostras. Na janela de vídeo, faça o
gesto da letra e pressione a tecla correspondente (A–Z) para gravar uma
rajada de 20 amostras; ESC encerra:

```bash
python -m libras.collect
```

Grave ao menos ~20 amostras por letra, variando levemente ângulo e
distância. O dataset fica em `data/dataset.csv`.

### 3. Executar o tradutor real

```bash
python -m libras.main                # webcam 0, dataset padrão
python -m libras.main --camera 1    # outra webcam
```

Conecte o monitor via HDMI e abra http://localhost:8001/ (ou acesse de
outra máquina da rede pelo IP da placa). O fluxo da câmera aparece no
painel esquerdo (MJPEG), com a letra reconhecida sobreposta.

### Como usar (gesticulando)

- **Letra**: mantenha o gesto estável por ~0,3 s (8 quadros dominando a
  janela de votação) — a letra é confirmada e entra na palavra.
- **Letra repetida** (ex.: "SS"): tire a mão do quadro por um instante e
  refaça o gesto.
- **Fim de palavra**: tire a mão do quadro por ~1 s — a palavra é exibida
  em destaque e falada pelo TTS.

Os limiares (confiança mínima, janela de votação, pausa de fim de palavra)
estão em [libras/config.py](libras/config.py).

---

## Testes unitários de requisitos

Cada arquivo de teste corresponde a um requisito das Tabelas 1 e 2 do
documento de arquitetura e implementa o cenário de teste ali descrito:

| Arquivo | Requisito | Cenário verificado |
|---|---|---|
| `test_rf01_interface.py` | RF-01 Interface de visualização | Frontend e APIs carregam corretamente, sem falhas |
| `test_rf02_webcam.py` | RF-02 Conexão da webcam | Recepção, processamento e exibição dos quadros |
| `test_rf03_reconhecimento.py` | RF-03 Reconhecimento de sinais | Alfabeto inteiro reconhecido; confirmação exige confiança + estabilidade |
| `test_rnf01_acessibilidade.py` | RNF-01 Acessibilidade | Comunicação só por sinais → saída dupla texto + voz |
| `test_rnf02_metricas.py` | RNF-02 Métricas de desempenho | Dashboard com CPI, clock etc.; benchmark comparável entre hardwares |
| `test_rnf03_portabilidade.py` | RNF-03 Portabilidade | Sistema autocontido: sem hardware, offline e com memória estável |

Para rodar (de dentro de `projeto/`):

```bash
python -m pytest            # suíte completa (~20 s)
python -m pytest tests/test_rf03_reconhecimento.py -v   # um requisito
```

Os testes rodam em qualquer máquina: os estágios de hardware (webcam,
MediaPipe) são substituídos por implementações sintéticas determinísticas;
todos os demais estágios exercitados são os de produção.

> Um teste é pulado conforme a plataforma: a falha de câmera com índice
> inválido só é testável onde o OpenCV está instalado (ex.: na Pi), e a
> degradação sem OpenCV só é testável onde ele está ausente.

---

## Benchmark de desempenho do processador

Atende ao requisito RNF-02: mede o desempenho do processador com cargas
padronizadas e produz um resultado comparável entre hardwares (ex.:
notebook × Raspberry Pi):

```bash
python -m libras.benchmark                     # completo (~30 s)
python -m libras.benchmark --rapido            # versão reduzida (~5 s)
python -m libras.benchmark --json resultado.json   # exporta p/ comparação
```

O relatório inclui:

- **Identificação da máquina** — processador, núcleos, sistema, e clock e
  temperatura antes/depois (evidencia *thermal throttling* na Pi);
- **inteiro_python** (MOPS) — laço de ALU em Python puro, sensível a clock/IPC;
- **flutuante_matmul** (GFLOPS) — multiplicação de matrizes via numpy/BLAS;
- **memoria_copia** (GB/s) — largura de banda de memória;
- **pipeline_traducao** (FPS) — o pipeline completo do projeto sem pausa
  entre quadros, com a latência média de cada estágio;
- **CPI e IPC** — ciclos por instrução medidos com `perf stat` sob carga
  (Linux; na Pi instale `linux-perf`). No Windows aparecem como
  indisponíveis;
- **Pontuação composta** — média geométrica das cargas (1000 = máquina de
  referência), para comparação direta entre hardwares.

Exemplo de saída (notebook de desenvolvimento):

```
==================================================================
BENCHMARK — Tradutor embarcado de LIBRAS
==================================================================
Máquina:      39A-NOT-0001 (Windows 11, AMD64)
Processador:  Intel64 Family 6 Model 154 Stepping 3, GenuineIntel
Núcleos:      12 físicos / 16 lógicos
...
carga               métrica       valor   descrição
inteiro_python      MOPS          23.08   2,000,000 iterações de inteiros...
flutuante_matmul    GFLOPS       127.06   multiplicação de matrizes 384×384
memoria_copia       GB/s          30.12   cópia de 64 MiB (leitura + escrita)
pipeline_traducao   FPS            95.4   300 quadros do pipeline completo
...
PONTUAÇÃO COMPOSTA: 1000.0 pontos
```

Rode com `--json` em cada máquina e compare os arquivos: a razão entre as
pontuações (e entre cada carga) quantifica a diferença de hardware prevista
no cenário de teste do requisito. Compare apenas execuções do mesmo modo
entre si (completo com completo, `--rapido` com `--rapido`): as cargas
reduzidas têm proporcionalmente mais overhead e produzem valores menores.

---

## Dashboard do processador (frontend)

O painel direito do frontend mostra, atualizado a cada segundo:

| Métrica | Fonte |
|---|---|
| Uso de CPU (total) e RAM | `psutil` |
| Taxa de clock (MHz) | `psutil.cpu_freq`, com fallback `vcgencmd measure_clock` (Pi) |
| Temperatura (°C) | `psutil`, `/sys/class/thermal`, ou `vcgencmd measure_temp` |
| CPI / IPC | `perf stat -a` (Linux com `perf` instalado) |
| FPS e latência por estágio | medidos pelo próprio pipeline |

Métricas sem fonte disponível na plataforma aparecem como "—" (o sistema
degrada graciosamente, nunca falha por falta de sensor).

---

## Solução de problemas

| Sintoma | Causa provável / solução |
|---|---|
| `mediapipe` não instala | Python sem wheel disponível ou SO 32-bit (`armv7l`). Use um Python suportado em SO 64-bit, ou rode `--demo` |
| `No matching distribution found for mediapipe` no Raspberry Pi | Python 3.13+: a última wheel `aarch64` de 0.10.x é a 0.10.18 e vai só até `cp312`. Confira com `python3 -V` e `pip index versions mediapipe` (se listar apenas `1.0.0`, é este caso). Solução: Python 3.12 via `uv venv -p 3.12` (veja Instalação) |
| `AttributeError: module 'mediapipe' has no attribute 'solutions'` | MediaPipe >= 0.10.31 (API nova) — suportado; rode `python -m libras.get_model` para baixar o modelo |
| `FATAL ERROR: this binary was compiled with aes enable but this feature is not available on this processor` + `Illegal instruction` | Wheel do `mediapipe` 1.x no Raspberry Pi: ela exige a extensão criptográfica ARMv8 (AES), que o Pi 4/5 não tem (confira com `grep -m1 Features /proc/cpuinfo` — sem `aes`). Instale abaixo do teto: `pip install "mediapipe>=0.10.9,<1.0"`. A linha `matplotlib ... generated new fontManager` que aparece antes é só log de INFO (o mediapipe depende do matplotlib), não a causa |
| `Modelo do MediaPipe não encontrado` | Rode `python -m libras.get_model` (download único de ~8 MB) |
| `CameraError: Não foi possível abrir a câmera` | Índice errado (`--camera 1`) ou permissão; em Linux confira `ls /dev/video*` |
| CPI/IPC "indisponível" | Instale `linux-perf` e libere `sudo sysctl kernel.perf_event_paranoid=0` (Linux). No Windows não há suporte |
| Sem áudio | Instale `espeak-ng` (`sudo apt install espeak-ng`) ou `pyttsx3`; o texto continua funcionando |
| Vídeo "indisponível neste modo" | Sem OpenCV instalado (ex.: modo demo no Windows) — tradução e dashboard seguem funcionando |
| Letras repetidas não entram | Comportamento esperado: tire a mão do quadro por um instante entre letras iguais |
| Reconhecimento fraco ao vivo | 1) grave amostras **suas** por cima do dataset importado (`python -m libras.collect` — maior ganho, pois casa a distribuição com a sua câmera/mão; a janela mostra a predição ao vivo, então dá para ver exatamente quais letras confundem e reforçá-las); 2) melhore a iluminação e aproxime a mão até preencher boa parte do quadro; 3) ajuste `min_confidence` em `libras/config.py` (0.55 confirma mais fácil, 0.80 erra menos) |

---

## Decisões de implementação (rastreabilidade com a arquitetura)

- **Dutos e filtros**: cada estágio é um módulo com contrato próprio
  (`FrameSource`, `LandmarkExtractor`…), substituível isoladamente — é o que
  permite o modo demo e os testes sem hardware (Seções 2 e 7.4 do documento).
- **Classificador k-NN sobre landmarks**: inferência = distância euclidiana
  sobre 42 floats; leve o suficiente para a Pi e robusto a fundo/iluminação
  (Seção 7.2). O modelo aprende com amostras coletadas pelo próprio usuário.
- **Suavização temporal**: votação em janela deslizante + limiar de
  confiança + liberação por pausa — implementação direta das Figuras 2 e 3
  (Seção 7.3).
- **Monitoramento**: CPI e clock derivam da equação de desempenho
  T_CPU = N_instr × CPI × T_clock (Hennessy & Patterson), medidos com
  `perf`/`vcgencmd`/`psutil` (Seção 7.5).
- **Edge computing**: nenhum estágio usa rede externa — verificado por teste
  automatizado (RNF-03), que bloqueia sockets e roda o pipeline completo.
