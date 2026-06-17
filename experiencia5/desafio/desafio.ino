#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <LittleFS.h>

const char* ssid     = "ESP32-SEMAFORO-jojima";
const char* password = "matusita_test";

const int PIN_LDR    = 4;
const int PIN_BTN    = 5;

const int BRILHO = 100;

const int ADC_RESOLUTION_BITS = 12;
const int ADC_MAX             = 4095;
int       limiarNoturno       = 1500;

const unsigned long INTERVALO_TELEMETRIA = 500;
const unsigned long DEBOUNCE_MS          = 50;

const unsigned long T_VERDE_MIN    = 3000;
const unsigned long T_AMARELO      = 1500;
const unsigned long T_VERMELHO_PED = 5000;
const unsigned long PERIODO_PISCA  = 500;

enum Fase { VERDE, AMARELO, VERMELHO, NOTURNO };
volatile Fase fase = VERDE;

unsigned long entrouNaFase = 0;

int           leituraLDR       = 0;
bool          ehNoite          = false;
unsigned long ultimaTelemetria = 0;

unsigned long ultimoPisca  = 0;
bool          amareloOn     = false;

volatile bool          pedidoTravessia = false;
volatile unsigned long ultimoIRQ       = 0;

void IRAM_ATTR isrPedestre() {
  unsigned long agora = millis();
  if (agora - ultimoIRQ >= DEBOUNCE_MS) {
    pedidoTravessia = true;
    ultimoIRQ = agora;
  }
}

void escreverRGB(bool r, bool g, bool b) {
  neopixelWrite(LED_BUILTIN,
                r ? BRILHO : 0,
                g ? BRILHO : 0,
                b ? BRILHO : 0);
}
void corOff()      { escreverRGB(false, false, false); }
void corVermelho() { escreverRGB(true,  false, false); }
void corAmarelo()  { escreverRGB(true,  true,  false); }
void corVerde()    { escreverRGB(false, true,  false); }

AsyncWebServer server(80);

const char* nomeFase(Fase f) {
  switch (f) {
    case VERDE:    return "VERDE";
    case AMARELO:  return "AMARELO";
    case VERMELHO: return "VERMELHO";
    case NOTURNO:  return "NOTURNO";
  }
  return "?";
}

void mudarFase(Fase nova, unsigned long agora) {
  fase         = nova;
  entrouNaFase = agora;
}

void setup() {
  Serial.begin(115200);

  analogReadResolution(ADC_RESOLUTION_BITS);

  pinMode(LED_BUILTIN, OUTPUT);
  corOff();

  pinMode(PIN_BTN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_BTN), isrPedestre, FALLING);

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

  server.on("/status", HTTP_GET, [](AsyncWebServerRequest *request){
    String json = "{";
    json += "\"ldr\":"     + String(leituraLDR) + ",";
    json += "\"adcMax\":"  + String(ADC_MAX)    + ",";
    json += "\"noite\":"   + String(ehNoite ? "true" : "false") + ",";
    json += "\"limiar\":"  + String(limiarNoturno) + ",";
    json += "\"fase\":\""  + String(nomeFase(fase)) + "\",";
    json += "\"pedido\":"  + String(pedidoTravessia ? "true" : "false");
    json += "}";
    request->send(200, "application/json", json);
  });

  server.on("/pedestre", HTTP_GET, [](AsyncWebServerRequest *request){
    pedidoTravessia = true;
    request->send(200, "text/plain", "Pedido de travessia registrado");
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
  mudarFase(VERDE, millis());
}

void loop() {
  unsigned long agora = millis();

  if (agora - ultimaTelemetria >= INTERVALO_TELEMETRIA) {
    ultimaTelemetria = agora;
    leituraLDR = analogRead(PIN_LDR);
    ehNoite    = (leituraLDR > limiarNoturno);
  }

  if (ehNoite && fase != NOTURNO) {
    mudarFase(NOTURNO, agora);
    ultimoPisca = agora;
    amareloOn   = false;
  } else if (!ehNoite && fase == NOTURNO) {
    mudarFase(VERMELHO, agora);
    corVermelho();
  }

  switch (fase) {

    case NOTURNO:
      if (agora - ultimoPisca >= PERIODO_PISCA) {
        ultimoPisca = agora;
        amareloOn   = !amareloOn;
        if (amareloOn) corAmarelo();
        else           corOff();
      }
      break;

    case VERDE:
      corVerde();
      if (pedidoTravessia && (agora - entrouNaFase >= T_VERDE_MIN)) {
        mudarFase(AMARELO, agora);
      }
      break;

    case AMARELO:
      corAmarelo();
      if (agora - entrouNaFase >= T_AMARELO) {
        mudarFase(VERMELHO, agora);
      }
      break;

    case VERMELHO:
      corVermelho();
      if (agora - entrouNaFase >= T_VERMELHO_PED) {
        pedidoTravessia = false;
        mudarFase(VERDE, agora);
      }
      break;
  }
}
