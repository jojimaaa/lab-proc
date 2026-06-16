#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <LittleFS.h>

// ---------------------------------------------------------------------------
// Aula 06 - DESAFIO: Semaforo Inteligente
//   - Modo Noturno Automatico (LDR): se escuro, pisca AMARELO a 1 Hz.
//   - Interrupcao de Pedestre: botao de travessia em pino de interrupcao.
//   - Logica de controle: durante o dia, ao pedir travessia, interrompe o
//     fluxo de transito com seguranca (verde -> amarelo -> vermelho).
//
// Hardware de saida: 1 LED RGB (catodo comum) simulando o semaforo.
//   VERMELHO = R   |   AMARELO = R + G   |   VERDE = G
// ---------------------------------------------------------------------------

const char* ssid     = "ESP32-SEMAFORO-jojima";
const char* password = "matusita_test";

// --- Pinos ---------------------------------------------------------------
const int PIN_LDR    = 4;   // entrada analogica (ADC) do LDR
const int PIN_BTN    = 5;   // botao de travessia (pedestre) -> interrupcao
const int PIN_LED_R  = 6;   // canal vermelho do LED RGB
const int PIN_LED_G  = 7;   // canal verde   do LED RGB
const int PIN_LED_B  = 15;  // canal azul    (nao usado, mantido OFF)

// --- ADC -----------------------------------------------------------------
// ADC nativo do ESP32: 12 bits => 0..4095 (2^12). (verificar datasheet)
const int ADC_RESOLUTION_BITS = 12;
const int ADC_MAX             = 4095;
int       limiarNoturno       = 1500;   // abaixo disso => "noite"

// --- Tempos (ms) ---------------------------------------------------------
const unsigned long INTERVALO_TELEMETRIA = 500;
const unsigned long DEBOUNCE_MS          = 50;

const unsigned long T_VERDE_MIN    = 3000;  // verde garante minimo antes de ceder
const unsigned long T_AMARELO      = 1500;  // amarelo de transicao (seguranca)
const unsigned long T_VERMELHO_PED = 5000;  // tempo de travessia do pedestre
const unsigned long PERIODO_PISCA  = 500;   // pisca amarelo a 1 Hz (500ms ON/OFF)

// --- Maquina de estados do semaforo --------------------------------------
enum Fase { VERDE, AMARELO, VERMELHO, NOTURNO };
volatile Fase fase = VERMELHO;

unsigned long entrouNaFase = 0;   // millis() ao entrar na fase atual

// --- Telemetria / LDR ----------------------------------------------------
int           leituraLDR       = 0;
bool          ehNoite          = false;
unsigned long ultimaTelemetria = 0;

// --- Pisca noturno -------------------------------------------------------
unsigned long ultimoPisca  = 0;
bool          amareloOn     = false;

// --- Interrupcao do pedestre ---------------------------------------------
volatile bool          pedidoTravessia = false;
volatile unsigned long ultimoIRQ       = 0;

// ISR curta: debounce por tempo + levanta a flag (tratada no loop).
void IRAM_ATTR isrPedestre() {
  unsigned long agora = millis();
  if (agora - ultimoIRQ >= DEBOUNCE_MS) {
    pedidoTravessia = true;
    ultimoIRQ = agora;
  }
}

// --- Controle do LED RGB -------------------------------------------------
void escreverRGB(bool r, bool g, bool b) {
  digitalWrite(PIN_LED_R, r ? HIGH : LOW);
  digitalWrite(PIN_LED_G, g ? HIGH : LOW);
  digitalWrite(PIN_LED_B, b ? HIGH : LOW);
}
void corOff()      { escreverRGB(false, false, false); }
void corVermelho() { escreverRGB(true,  false, false); }
void corAmarelo()  { escreverRGB(true,  true,  false); }  // R + G
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

  pinMode(PIN_LED_R, OUTPUT);
  pinMode(PIN_LED_G, OUTPUT);
  pinMode(PIN_LED_B, OUTPUT);
  corOff();

  // Botao de travessia por interrupcao de HARDWARE (pull-up interno).
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

  // Telemetria do semaforo (polling pelo navegador, >= 1 Hz).
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

  // Permite solicitar a travessia tambem pela interface (alem do botao).
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
  mudarFase(VERMELHO, millis());
}

void loop() {
  unsigned long agora = millis();

  // -----------------------------------------------------------------------
  // 1) TELEMETRIA (polling) - leitura do LDR e deteccao de noite.
  // -----------------------------------------------------------------------
  if (agora - ultimaTelemetria >= INTERVALO_TELEMETRIA) {
    ultimaTelemetria = agora;
    leituraLDR = analogRead(PIN_LDR);
    ehNoite    = (leituraLDR < limiarNoturno);
  }

  // -----------------------------------------------------------------------
  // 2) MODO NOTURNO AUTOMATICO
  //    Se escureceu, entra em alerta (pisca amarelo a 1 Hz), independente
  //    da fase atual. Quando amanhece, retoma o ciclo em VERMELHO seguro.
  // -----------------------------------------------------------------------
  if (ehNoite && fase != NOTURNO) {
    mudarFase(NOTURNO, agora);
    ultimoPisca = agora;
    amareloOn   = false;
  } else if (!ehNoite && fase == NOTURNO) {
    mudarFase(VERMELHO, agora);
    corVermelho();
  }

  // -----------------------------------------------------------------------
  // 3) MAQUINA DE ESTADOS DO SEMAFORO
  // -----------------------------------------------------------------------
  switch (fase) {

    case NOTURNO:
      // Alerta noturno: pisca amarelo a 1 Hz.
      if (agora - ultimoPisca >= PERIODO_PISCA) {
        ultimoPisca = agora;
        amareloOn   = !amareloOn;
        if (amareloOn) corAmarelo();
        else           corOff();
      }
      break;

    case VERDE:
      corVerde();
      // Durante o dia: se ha pedido de travessia e o verde ja durou o
      // minimo de seguranca, inicia a transicao (verde -> amarelo).
      if (pedidoTravessia && (agora - entrouNaFase >= T_VERDE_MIN)) {
        mudarFase(AMARELO, agora);
      }
      break;

    case AMARELO:
      corAmarelo();
      // Amarelo de transicao: garante parada segura antes do vermelho.
      if (agora - entrouNaFase >= T_AMARELO) {
        mudarFase(VERMELHO, agora);
      }
      break;

    case VERMELHO:
      corVermelho();
      if (pedidoTravessia) {
        // Atende a travessia: mantem vermelho pelo tempo de travessia.
        if (agora - entrouNaFase >= T_VERMELHO_PED) {
          pedidoTravessia = false;   // pedido atendido
          mudarFase(VERDE, agora);
        }
      } else {
        // Sem pedido: apos o tempo de travessia, libera o transito (verde).
        if (agora - entrouNaFase >= T_VERMELHO_PED) {
          mudarFase(VERDE, agora);
        }
      }
      break;
  }
}
