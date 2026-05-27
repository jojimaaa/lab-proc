#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <LittleFS.h>

// --- Wi-Fi Access Point ---
const char* ssid = "ESP32-CALC";
const char* password = "matusita_test";

// --- Mapeamento dos LEDs (GPIOs da ESP32-C3) ---
const int LED_BIT0 = 7;  // LSB
const int LED_BIT1 = 6;
const int LED_BIT2 = 5;
const int LED_BIT3 = 4;  // MSB (Sinal)

AsyncWebServer server(80);

// --- Funções Auxiliares de Lógica ---
int twos4_to_int(int v4) {
  v4 &= 0x0F;
  return (v4 & 0x08) ? (v4 - 16) : v4;
}

String to_bin4(int v4) {
  v4 &= 0x0F;
  String s = "";
  for (int i = 3; i >= 0; i--) s += ((v4 >> i) & 1) ? '1' : '0';
  return s;
}

void escreverLEDs(int v4) {
  v4 &= 0x0F;
  digitalWrite(LED_BIT0, (v4 >> 0) & 0x01);
  digitalWrite(LED_BIT1, (v4 >> 1) & 0x01);
  digitalWrite(LED_BIT2, (v4 >> 2) & 0x01);
  digitalWrite(LED_BIT3, (v4 >> 3) & 0x01);
}

void setup() {
  Serial.begin(115200);

  // Configuração dos Pinos
  pinMode(LED_BIT0, OUTPUT);
  pinMode(LED_BIT1, OUTPUT);
  pinMode(LED_BIT2, OUTPUT);
  pinMode(LED_BIT3, OUTPUT);
  escreverLEDs(0);

  // Inicializa LittleFS
  if(!LittleFS.begin()){
    Serial.println("Erro ao montar LittleFS");
  }

  // Inicia Access Point
  WiFi.softAP(ssid, password);
  Serial.print("IP da ESP32: ");
  Serial.println(WiFi.softAPIP());

  // --- ROTA 1: Serve o HTML ---
  server.on("/", HTTP_GET, [](AsyncWebServerRequest *request){
    request->send(LittleFS, "/index.html", "text/html");
  });

  // --- ROTA 2: Lógica da Calculadora ---
  server.on("/calc", HTTP_GET, [](AsyncWebServerRequest *request){
    
    if (request->hasParam("a") && request->hasParam("b") && request->hasParam("op")) {
      String paramA = request->getParam("a")->value();
      String paramB = request->getParam("b")->value();
      String op     = request->getParam("op")->value();

      int valA4 = (int) strtol(paramA.c_str(), NULL, 2) & 0x0F;
      int valB4 = (int) strtol(paramB.c_str(), NULL, 2) & 0x0F;
      int signedA = twos4_to_int(valA4);
      int signedB = twos4_to_int(valB4);

      int resultadoFull, operandoB_efetivo;

      if (op == "add") {
        resultadoFull = signedA + signedB;
        operandoB_efetivo = signedB;
      } else {
        resultadoFull = signedA - signedB;
        operandoB_efetivo = -signedB;
      }

      int resultado4 = resultadoFull & 0x0F;
      int resultadoSigned = twos4_to_int(resultado4);

      bool sinalA = (signedA < 0);
      bool sinalB = (operandoB_efetivo < 0);
      bool sinalR = (resultadoSigned < 0);
      bool overflow = (sinalA == sinalB) && (sinalA != sinalR);

      // Hardware: LEDs
      escreverLEDs(resultado4);

      // Resposta formatada
      String body = "A=" + to_bin4(valA4) + " (" + String(signedA) + ")\n";
      body += "B=" + to_bin4(valB4) + " (" + String(signedB) + ")\n";
      body += "OP=" + op + "\n";
      body += "RES=" + to_bin4(resultado4) + " (" + String(resultadoSigned) + ")\n";
      body += "OVERFLOW=" + String(overflow ? 1 : 0);

      request->send(200, "text/plain", body);
    } else {
      request->send(400, "text/plain", "Faltam parametros");
    }
  });

  server.begin();
}

void loop() {}