#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <LittleFS.h>

// --- Wi-Fi Access Point ---
const char* ssid = "ESP32-PWM";
const char* password = "matusita_test";

// --- Mapeamento de pinos (GPIOs da ESP32-C3) ---
const int PIN_LED = 7;

// LED brilha sem cintilacao perceptivel em alta frequencia. Usamos 5 kHz
// com 8 bits de resolucao (duty de 0 a 255), faixa classica de PWM de LED.
// (Core ESP32 3.x: a API LEDC nova trabalha por PINO; o canal e gerenciado
//  internamente pelo core.)
const int LEDC_FREQ_LED = 5000;  // 5 kHz -> sem flicker visivel
const int LEDC_RES_LED  = 8;     // 8 bits -> duty 0..255
const int DUTY_MAX_LED  = 255;   // (1 << LEDC_RES_LED) - 1

AsyncWebServer server(80);

// --- Funcoes auxiliares ---

int percentToDuty(int pct) {
  if (pct < 0)   pct = 0;
  if (pct > 100) pct = 100;
  return (pct * DUTY_MAX_LED) / 100;
}

void aplicarBrilhoLED(int pct) {
  ledcWrite(PIN_LED, percentToDuty(pct));
}

void setup() {
  Serial.begin(115200);

  // API LEDC 3.x: configura frequencia/resolucao e liga o pino de uma vez.
  ledcAttach(PIN_LED, LEDC_FREQ_LED, LEDC_RES_LED);
  aplicarBrilhoLED(0);

  if (!LittleFS.begin()) {
    Serial.println("Erro ao montar LittleFS");
  }

  WiFi.softAP(ssid, password);
  Serial.print("IP da ESP32: ");
  Serial.println(WiFi.softAPIP());

  server.on("/", HTTP_GET, [](AsyncWebServerRequest *request){
    request->send(LittleFS, "/index.html", "text/html");
  });

  server.on("/led", HTTP_GET, [](AsyncWebServerRequest *request){
    if (!request->hasParam("val")) {
      request->send(400, "text/plain", "Falta parametro 'val'");
      return;
    }

    int pct = request->getParam("val")->value().toInt();
    if (pct < 0 || pct > 100) {
      request->send(400, "text/plain", "val invalido (use 0..100)");
      return;
    }

    aplicarBrilhoLED(pct);

    int duty = percentToDuty(pct);
    String body = "LED=" + String(pct) + "%\n";
    body += "DUTY=" + String(duty) + "/" + String(DUTY_MAX_LED) + "\n";
    body += "FREQ_Hz=" + String(LEDC_FREQ_LED);
    request->send(200, "text/plain", body);
  });

  server.begin();
}

void loop() {
}
