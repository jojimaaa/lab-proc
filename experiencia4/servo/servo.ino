#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <LittleFS.h>

// =====================================================================
// Lab 5 - Plano de Bancada 3: Controle Posicional Eletromecanico (Servo)
//
// A interface web atua como um slider (0..180 graus) que comanda a
// posicao de um servo motor. O sinal e gerado pelo periferico dedicado
// LEDC do ESP32 (PWM em hardware), liberando a CPU (I/O nao bloqueante).
//
// Servo hobby: periodo de 20 ms (50 Hz). A POSICAO e definida pela
// LARGURA do pulso ativo dentro do periodo (pag. 9 do blueprint):
//   1.0 ms -> 0 graus ; 1.5 ms -> 90 graus ; 2.0 ms -> 180 graus
//
// ATENCAO (pag. 9): o ESP32 fornece o sinal logico de 3.3V, mas o motor
// deve ser alimentado de forma adequada (V-IN ou fonte externa de 5V),
// com GND comum entre a fonte e o ESP32.
// =====================================================================

// --- Wi-Fi Access Point ---
const char* ssid = "ESP32-PWM";
const char* password = "matusita_test";

// --- Mapeamento de pinos (GPIOs da ESP32-C3) ---
const int PIN_SERVO = 6;  // saida do sinal de controle do servo (3.3V logico)

// --- Configuracao do canal LEDC para o servo ---
// 16 bits de resolucao para ter passos finos de duty dentro do periodo.
const int LEDC_CH_SERVO    = 1;       // canal LEDC dedicado ao servo
const int LEDC_FREQ_SERVO  = 50;      // 50 Hz -> periodo de 20 ms
const int LEDC_RES_SERVO   = 16;      // 16 bits -> duty 0..65535
const int SERVO_PERIODO_us = 20000;   // 1/50 Hz = 20000 us
const int SERVO_MIN_us     = 1000;    // pulso para 0 graus
const int SERVO_MAX_us     = 2000;    // pulso para 180 graus
const long DUTY_FULL_SERVO = 65535;   // (1 << LEDC_RES_SERVO) - 1

AsyncWebServer server(80);

// --- Funcoes auxiliares ---

// angulo 0..180 -> duty de 16 bits, em dois passos:
// 1) angulo -> largura do pulso (us), interpolacao linear entre MIN e MAX;
// 2) largura -> duty: duty = (pulso / periodo) * duty_cheio.
long anguloParaDuty(int ang) {
  if (ang < 0)   ang = 0;
  if (ang > 180) ang = 180;
  long pulso_us = SERVO_MIN_us +
                  (long)(SERVO_MAX_us - SERVO_MIN_us) * ang / 180;
  return DUTY_FULL_SERVO * pulso_us / SERVO_PERIODO_us;
}

// Aplica a posicao (0..180 graus) no servo via hardware LEDC.
void aplicarAnguloServo(int ang) {
  ledcWrite(LEDC_CH_SERVO, anguloParaDuty(ang));
}

void setup() {
  Serial.begin(115200);

  // --- Configura o canal PWM de hardware (LEDC) para o servo ---
  ledcSetup(LEDC_CH_SERVO, LEDC_FREQ_SERVO, LEDC_RES_SERVO);
  ledcAttachPin(PIN_SERVO, LEDC_CH_SERVO);
  aplicarAnguloServo(0);  // comeca em 0 graus

  // Inicializa LittleFS
  if (!LittleFS.begin()) {
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

  // --- ROTA 2: Controle de posicao do servo via PWM ---
  // GET /servo?val=<0..180>   -> ajusta a largura do pulso (posicao).
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

    aplicarAnguloServo(ang);  // atuacao fisica em hardware (nao bloqueante)

    long pulso_us = SERVO_MIN_us +
                    (long)(SERVO_MAX_us - SERVO_MIN_us) * ang / 180;
    String body = "SERVO=" + String(ang) + " graus\n";
    body += "PULSO_us=" + String(pulso_us) + "\n";
    body += "DUTY=" + String(anguloParaDuty(ang)) + "/" + String(DUTY_FULL_SERVO) + "\n";
    body += "FREQ_Hz=" + String(LEDC_FREQ_SERVO);
    request->send(200, "text/plain", body);
  });

  server.begin();
}

void loop() {
  // CPU livre: o PWM e mantido pelo hardware LEDC, nao pelo loop.
}
