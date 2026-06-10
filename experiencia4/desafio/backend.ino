#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <LittleFS.h>

const char* ssid = "ESP32-PWM";
const char* password = "matusita_test";

const int PIN_LED   = 7;  
const int PIN_SERVO = 6;

const int LEDC_CH_LED   = 0;
const int LEDC_FREQ_LED = 5000; 
const int LEDC_RES_LED  = 8; 
const int DUTY_MAX_LED  = 255;

const int LEDC_CH_SERVO   = 1;
const int LEDC_FREQ_SERVO = 50;    
const int LEDC_RES_SERVO  = 16;    
const int SERVO_PERIODO_us = 20000;       
const int SERVO_MIN_us     = 1000;        
const int SERVO_MAX_us     = 2000;        
const long DUTY_FULL_SERVO = 65535;       

AsyncWebServer server(80);

int percentToDuty(int pct) {
  if (pct < 0)   pct = 0;
  if (pct > 100) pct = 100;
  return (pct * DUTY_MAX_LED) / 100;
}

void aplicarBrilhoLED(int pct) {
  ledcWrite(LEDC_CH_LED, percentToDuty(pct));
}

long anguloParaDuty(int ang) {
  if (ang < 0)   ang = 0;
  if (ang > 180) ang = 180;
  long pulso_us = SERVO_MIN_us +
                  (long)(SERVO_MAX_us - SERVO_MIN_us) * ang / 180;
  return DUTY_FULL_SERVO * pulso_us / SERVO_PERIODO_us;
}

void aplicarAnguloServo(int ang) {
  ledcWrite(LEDC_CH_SERVO, anguloParaDuty(ang));
}

void setup() {
  Serial.begin(115200);

  ledcSetup(LEDC_CH_LED, LEDC_FREQ_LED, LEDC_RES_LED);
  ledcAttachPin(PIN_LED, LEDC_CH_LED);
  aplicarBrilhoLED(0); 

  ledcSetup(LEDC_CH_SERVO, LEDC_FREQ_SERVO, LEDC_RES_SERVO);
  ledcAttachPin(PIN_SERVO, LEDC_CH_SERVO);
  aplicarAnguloServo(0);  

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
    body += "FREQ_Hz=" + String(LEDC_FREQ_LED);
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

    aplicarAnguloServo(ang);

    long pulso_us = SERVO_MIN_us + (long)(SERVO_MAX_us - SERVO_MIN_us) * ang / 180;
    String body = "SERVO=" + String(ang) + " graus\n";
    body += "PULSO_us=" + String(pulso_us) + "\n";
    body += "DUTY=" + String(anguloParaDuty(ang)) + "/" + String(DUTY_FULL_SERVO) + "\n";
    body += "FREQ_Hz=" + String(LEDC_FREQ_SERVO);
    request->send(200, "text/plain", body);
  });

  server.begin();
}

void loop() {
}
