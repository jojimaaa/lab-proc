#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <LittleFS.h>
#include <ESP32Servo.h>

const char* ssid = "ESP32-PWM-jojima";
const char* password = "matusita_test";

const int PIN_LED   = 7;
const int PIN_SERVO = 6;

const int LEDC_RES_LED = 13;
const int DUTY_MAX_LED = 8191;

const int FREQ_LED_MIN = 1;
const int FREQ_LED_MAX = 4000;

int freqLED   = 4000;
int brilhoLED = 0;

Servo meuServo;
AsyncWebServer server(80);

int percentToDuty(int pct) {
  if (pct < 0)   pct = 0;
  if (pct > 100) pct = 100;
  return (pct * DUTY_MAX_LED) / 100;
}

void aplicarBrilhoLED(int pct) {
  brilhoLED = pct;
  ledcWrite(PIN_LED, percentToDuty(pct));
}

void aplicarFreqLED(int hz) {
  freqLED = hz;
  ledcChangeFrequency(PIN_LED, hz, LEDC_RES_LED);
  ledcWrite(PIN_LED, percentToDuty(brilhoLED));
}

void setup() {
  Serial.begin(115200);

  ledcAttach(PIN_LED, freqLED, LEDC_RES_LED);
  aplicarBrilhoLED(0);

  meuServo.attach(PIN_SERVO);
  meuServo.write(0);

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

    String body = "LED=" + String(pct) + "%\n";
    body += "DUTY=" + String(percentToDuty(pct)) + "/" + String(DUTY_MAX_LED) + "\n";
    body += "FREQ_Hz=" + String(freqLED);
    request->send(200, "text/plain", body);
  });

  server.on("/freq", HTTP_GET, [](AsyncWebServerRequest *request){
    if (!request->hasParam("val")) {
      request->send(400, "text/plain", "Falta parametro 'val'");
      return;
    }
    int hz = request->getParam("val")->value().toInt();
    if (hz < FREQ_LED_MIN || hz > FREQ_LED_MAX) {
      request->send(400, "text/plain",
                    "freq invalida (use " + String(FREQ_LED_MIN) +
                    ".." + String(FREQ_LED_MAX) + " Hz)");
      return;
    }

    aplicarFreqLED(hz);

    String body = "FREQ_Hz=" + String(freqLED) + "\n";
    body += "LED=" + String(brilhoLED) + "%";
    request->send(200, "text/plain", body);
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
