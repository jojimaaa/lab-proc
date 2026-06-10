#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <LittleFS.h>
#include <ESP32Servo.h>

const char* ssid = "ESP32-PWM-jojima";
const char* password = "matusita_test";

const int PIN_SERVO = 6;

Servo meuServo;
AsyncWebServer server(80);

void setup() {
  Serial.begin(115200);

  meuServo.attach(PIN_SERVO);
  meuServo.write(0);

  if (!LittleFS.begin()) {
    Serial.println("Erro ao montar LittleFS");
  }

  WiFi.softAP(ssid, password);
  Serial.print("IP da ESP32: ");
  Serial.println(WiFi.softAPIP());

  server.on("/", HTTP_GET, [](AsyncWebServerRequest *request){
    request->send(LittleFS, "/index.html", "text/html");
  });

  server.on("/servo", HTTP_GET, [](AsyncWebServerRequest *request){
    if (!request->hasParam("val")) {
      request->send(400, "text/plain", "Falta parametro 'val'");
      return;
    }

    int ang = request->getParam("val")->value().toInt();
    if (ang < 0 || ang > 180) {
      request->send(400, "text/plain", "val invalido (use 0..180)");
      return;
    }

    meuServo.write(ang);

    String body = "SERVO=" + String(ang) + " graus\n";
    body += "PULSO_us=" + String(meuServo.readMicroseconds()) + "\n";
    body += "FREQ_Hz=50";
    request->send(200, "text/plain", body);
  });

  server.begin();
}

void loop() {
}
