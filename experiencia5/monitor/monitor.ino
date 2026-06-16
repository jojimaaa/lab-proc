#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <LittleFS.h>

// ---------------------------------------------------------------------------
// Aula 06 - Sistema de Monitoramento Inteligente
// LDR (ADC) + Webserver + Botao SOS (interrupcao de HW) + LED RGB (estados)
// ---------------------------------------------------------------------------

const char* ssid     = "ESP32-MONITOR-jojima";
const char* password = "matusita_test";

// --- Pinos ---------------------------------------------------------------
const int PIN_LDR    = 4;   // entrada analogica (ADC) do sensor LDR
const int PIN_BTN    = 5;   // botao SOS -> pino de interrupcao
const int PIN_LED_R  = 6;   // canal vermelho do LED RGB
const int PIN_LED_G  = 7;   // canal verde   do LED RGB
const int PIN_LED_B  = 15;  // canal azul    do LED RGB (nao usado, deixado OFF)

// --- ADC -----------------------------------------------------------------
// O ADC do ESP32 (SAR) tem resolucao nativa de 12 bits => 0..4095 (2^12).
// Referencia (verificar no relatorio - datasheet): ESPRESSIF SYSTEMS.
//   ESP32 Series Datasheet. Secao "ADC". A leitura analogRead() devolve
//   valores de 0 a 4095 quando a resolucao padrao (12 bits) esta ativa.
const int ADC_RESOLUTION_BITS = 12;
const int ADC_MAX             = 4095;      // 2^12 - 1

// Limiar de "baixa luminosidade" para entrar em modo noturno.
// Quanto MENOR a leitura, mais escuro (depende do divisor com o LDR).
// Ajuste conforme o ambiente / montagem.
int limiarNoturno = 1500;

// --- Tempos (ms) ---------------------------------------------------------
const unsigned long INTERVALO_TELEMETRIA = 500;   // leitura LDR >= 1 Hz (2 Hz aqui)
const unsigned long PERIODO_PISCA        = 2000;  // pisca amarelo a cada 2 s (modo noturno)
const unsigned long DURACAO_SOS          = 3000;  // vermelho fixo por 3 s
const unsigned long DEBOUNCE_MS          = 50;    // janela de debounce do botao

// --- Estado da maquina de estados do LED --------------------------------
enum EstadoLED { NORMAL, NOTURNO, EMERGENCIA };
volatile EstadoLED estado = NORMAL;

// --- Variaveis de leitura / telemetria ----------------------------------
int           leituraLDR    = 0;       // ultimo valor lido do ADC (0..4095)
bool          ehNoite       = false;   // luminosidade abaixo do limiar?
unsigned long ultimaTelemetria = 0;

// --- Pisca (modo noturno) ------------------------------------------------
unsigned long ultimoPisca = 0;
bool          ledAmareloOn = false;

// --- Interrupcao SOS -----------------------------------------------------
// Flag setada pela ISR e tratada no loop (ISR curta = boa pratica).
volatile bool          sosSolicitado    = false;
volatile unsigned long ultimoIRQ        = 0;   // p/ debounce dentro da ISR
unsigned long          inicioEmergencia = 0;   // momento em que o SOS comecou

// ISR do botao SOS: mantida curta. Apenas faz o debounce por tempo
// (millis() pode ser usado dentro da ISR no ESP32) e levanta a flag.
void IRAM_ATTR isrBotaoSOS() {
  unsigned long agora = millis();
  if (agora - ultimoIRQ >= DEBOUNCE_MS) {   // ignora ruido/bouncing
    sosSolicitado = true;
    ultimoIRQ = agora;
  }
}

// --- Controle do LED RGB -------------------------------------------------
// LED RGB de catodo comum: HIGH acende o canal. Amarelo = R + G.
void escreverRGB(bool r, bool g, bool b) {
  digitalWrite(PIN_LED_R, r ? HIGH : LOW);
  digitalWrite(PIN_LED_G, g ? HIGH : LOW);
  digitalWrite(PIN_LED_B, b ? HIGH : LOW);
}

void ledOff()      { escreverRGB(false, false, false); }
void ledAmarelo()  { escreverRGB(true,  true,  false); }  // R + G
void ledVermelho() { escreverRGB(true,  false, false); }

AsyncWebServer server(80);

const char* nomeEstado(EstadoLED e) {
  switch (e) {
    case NORMAL:     return "NORMAL";
    case NOTURNO:    return "NOTURNO";
    case EMERGENCIA: return "EMERGENCIA";
  }
  return "?";
}

void setup() {
  Serial.begin(115200);

  // --- ADC ---
  analogReadResolution(ADC_RESOLUTION_BITS);   // garante 12 bits (0..4095)

  // --- LED RGB ---
  pinMode(PIN_LED_R, OUTPUT);
  pinMode(PIN_LED_G, OUTPUT);
  pinMode(PIN_LED_B, OUTPUT);
  ledOff();

  // --- Botao SOS por interrupcao de HARDWARE ---
  // Pull-up interno: botao liga o pino ao GND => borda de descida (FALLING).
  pinMode(PIN_BTN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_BTN), isrBotaoSOS, FALLING);

  // --- Webserver (Access Point) ---
  if (!LittleFS.begin()) {
    Serial.println("Erro ao montar LittleFS");
  }

  if (!WiFi.softAP(ssid, password)) {
    Serial.println("FALHA: nao foi possivel iniciar o Access Point");
  } else {
    Serial.print("IP da ESP32: ");
    Serial.println(WiFi.softAPIP());
  }

  server.on("/", HTTP_GET, [](AsyncWebServerRequest *request){
    request->send(LittleFS, "/index.html", "text/html");
  });

  // Endpoint de telemetria: devolve JSON com a ultima leitura do LDR.
  // O navegador faz polling deste endpoint (>= 1 Hz).
  server.on("/ldr", HTTP_GET, [](AsyncWebServerRequest *request){
    String json = "{";
    json += "\"ldr\":"       + String(leituraLDR) + ",";
    json += "\"adcMax\":"    + String(ADC_MAX)    + ",";
    json += "\"noite\":"     + String(ehNoite ? "true" : "false") + ",";
    json += "\"limiar\":"    + String(limiarNoturno) + ",";
    json += "\"estado\":\""  + String(nomeEstado(estado)) + "\"";
    json += "}";
    request->send(200, "application/json", json);
  });

  // Permite ajustar o limiar do modo noturno pela interface.
  server.on("/limiar", HTTP_GET, [](AsyncWebServerRequest *request){
    if (!request->hasParam("val")) {
      request->send(400, "text/plain", "Falta parametro 'val'");
      return;
    }
    int v = request->getParam("val")->value().toInt();
    if (v < 0 || v > ADC_MAX) {
      request->send(400, "text/plain", "val invalido (use 0.." + String(ADC_MAX) + ")");
      return;
    }
    limiarNoturno = v;
    request->send(200, "text/plain", "LIMIAR=" + String(limiarNoturno));
  });

  server.begin();
}

void loop() {
  unsigned long agora = millis();

  // -----------------------------------------------------------------------
  // 1) TELEMETRIA DE FUNDO (polling, baixa prioridade) - leitura do LDR
  //    Roda a >= 1 Hz no loop principal, sem bloquear (sem delay()).
  // -----------------------------------------------------------------------
  if (agora - ultimaTelemetria >= INTERVALO_TELEMETRIA) {
    ultimaTelemetria = agora;
    leituraLDR = analogRead(PIN_LDR);
    ehNoite    = (leituraLDR < limiarNoturno);

    Serial.printf("LDR=%d  noite=%d  estado=%s\n",
                  leituraLDR, ehNoite, nomeEstado(estado));
  }

  // -----------------------------------------------------------------------
  // 2) TRATAMENTO DA INTERRUPCAO SOS (prioridade maxima)
  //    A ISR so levantou a flag; a acao acontece aqui no loop.
  // -----------------------------------------------------------------------
  if (sosSolicitado) {
    sosSolicitado    = false;
    estado           = EMERGENCIA;
    inicioEmergencia = agora;
    ledVermelho();                       // VERMELHO fixo imediato
    Serial.println(">>> SOS! LED VERMELHO por 3 s");
  }

  // -----------------------------------------------------------------------
  // 3) MAQUINA DE ESTADOS DO LED
  // -----------------------------------------------------------------------
  switch (estado) {

    case EMERGENCIA:
      // Mantem vermelho fixo por DURACAO_SOS; depois volta ao estado normal.
      if (agora - inicioEmergencia >= DURACAO_SOS) {
        estado = ehNoite ? NOTURNO : NORMAL;
        ledOff();
      }
      break;

    case NORMAL:
      // Luminosidade normal -> LED apagado.
      if (ehNoite) {
        estado = NOTURNO;
      } else {
        ledOff();
      }
      break;

    case NOTURNO:
      // Baixa luminosidade -> pisca AMARELO a cada 2 s.
      if (!ehNoite) {
        estado = NORMAL;
        ledOff();
      } else if (agora - ultimoPisca >= PERIODO_PISCA) {
        ultimoPisca  = agora;
        ledAmareloOn = !ledAmareloOn;
        if (ledAmareloOn) ledAmarelo();
        else              ledOff();
      }
      break;
  }
}
