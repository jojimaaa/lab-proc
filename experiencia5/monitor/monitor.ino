#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <LittleFS.h>

const char* ssid     = "ESP32-MONITOR-jojima";
const char* password = "matusita_test";

const int PIN_LDR    = 4;
const int PIN_BTN    = 5;

const int BRILHO = 100;

const int ADC_RESOLUTION_BITS = 12;
const int ADC_MAX             = 4095;

int limiarNoturno = 1500;

const unsigned long INTERVALO_TELEMETRIA = 500;
const unsigned long PERIODO_PISCA        = 500;
const unsigned long DURACAO_SOS          = 3000;
const unsigned long PERIODO_PISCA_SOS    = 250;
const unsigned long DEBOUNCE_MS          = 50;

enum EstadoLED { NORMAL, NOTURNO, EMERGENCIA };
volatile EstadoLED estado = NORMAL;

int           leituraLDR    = 0;
bool          ehNoite       = false;
unsigned long ultimaTelemetria = 0;

unsigned long ultimoPisca = 0;
bool          ledAmareloOn = false;

volatile bool          sosSolicitado    = false;
volatile unsigned long ultimoIRQ        = 0;
unsigned long          inicioEmergencia = 0;
unsigned long          ultimoPiscaSOS   = 0;
bool                   ledVermelhoOn    = false;

void IRAM_ATTR isrBotaoSOS() {
  unsigned long agora = millis();
  if (agora - ultimoIRQ >= DEBOUNCE_MS) {
    sosSolicitado = true;
    ultimoIRQ = agora;
  }
}

void escreverRGB(bool r, bool g, bool b) {
  neopixelWrite(LED_BUILTIN,
                r ? BRILHO : 0,
                g ? BRILHO : 0,
                b ? BRILHO : 0);
}

void ledOff()      { escreverRGB(false, false, false); }
void ledAmarelo()  { escreverRGB(true,  true,  false); }
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

  analogReadResolution(ADC_RESOLUTION_BITS);

  pinMode(LED_BUILTIN, OUTPUT);
  ledOff();

  pinMode(PIN_BTN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_BTN), isrBotaoSOS, FALLING);

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

  if (agora - ultimaTelemetria >= INTERVALO_TELEMETRIA) {
    ultimaTelemetria = agora;
    leituraLDR = analogRead(PIN_LDR);
    ehNoite    = (leituraLDR > limiarNoturno);

    Serial.printf("LDR=%d  noite=%d  estado=%s\n",
                  leituraLDR, ehNoite, nomeEstado(estado));
  }

  if (sosSolicitado) {
    sosSolicitado    = false;
    estado           = EMERGENCIA;
    inicioEmergencia = agora;
    ultimoPiscaSOS   = agora;
    ledVermelhoOn    = true;
    ledVermelho();
    Serial.println(">>> SOS! LED BUILTIN piscando VERMELHO por 3 s");
  }

  switch (estado) {

    case EMERGENCIA:
      if (agora - inicioEmergencia >= DURACAO_SOS) {
        estado = ehNoite ? NOTURNO : NORMAL;
        ledOff();
      } else if (agora - ultimoPiscaSOS >= PERIODO_PISCA_SOS) {
        ultimoPiscaSOS = agora;
        ledVermelhoOn  = !ledVermelhoOn;
        if (ledVermelhoOn) ledVermelho();
        else               ledOff();
      }
      break;

    case NORMAL:
      if (ehNoite) {
        estado = NOTURNO;
      } else {
        ledOff();
      }
      break;

    case NOTURNO:
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
