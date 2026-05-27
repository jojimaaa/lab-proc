#include <WiFi.h>
#include <ESPAsyncWebServer.h>

// Configurações da Rede
const char* ssid = "ESP32_Health_Check";
const char* password = "matusita_test";

AsyncWebServer server(80);

void setup() {
  Serial.begin(115200);

  WiFi.softAP(ssid, password);

  Serial.println("Rede Criada!");
  Serial.print("IP da ESP32: ");
  Serial.println(WiFi.softAPIP());

  // Endpoint /health: Responde com status 200 e mensagem "OK"
  server.on("/health", HTTP_GET, [](AsyncWebServerRequest *request){
    request->send(200, "text/plain", "OK - ESP32 is running");
  });

  server.begin();
}

void loop() {
}