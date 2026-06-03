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
const int LED_BIT3 = 4;  // MSB (Sinal) no modo 4 bits

// Largura maxima suportada para os operandos (complemento de dois)
const int MAX_BITS = 32;

AsyncWebServer server(80);

// --- Funções Auxiliares de Lógica (parametrizadas pelo nº de bits) ---

// mascara com 'bits' bits 1 (ex.: bits=4 -> 0x0F)
long long maskN(int bits) {
  if (bits >= 64) return ~0LL;
  return (1LL << bits) - 1LL;
}

// interpreta um valor de 'bits' bits em complemento de dois
long long twos_to_int(long long v, int bits) {
  v &= maskN(bits);
  long long signBit = 1LL << (bits - 1);
  return (v & signBit) ? (v - (1LL << bits)) : v;
}

// representacao binaria com exatamente 'bits' dígitos
String to_bin(long long v, int bits) {
  v &= maskN(bits);
  String s = "";
  for (int i = bits - 1; i >= 0; i--) s += ((v >> i) & 1) ? '1' : '0';
  return s;
}

// Escreve nos 4 LEDs físicos (apenas usado no modo 4 bits)
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

      // Novo parâmetro: número de bits dos operandos (padrão 4)
      int bits = 4;
      if (request->hasParam("bits")) {
        bits = request->getParam("bits")->value().toInt();
      }
      if (bits < 1 || bits > MAX_BITS) {
        request->send(400, "text/plain",
                      "bits invalido (use 1.." + String(MAX_BITS) + ")");
        return;
      }

      long long mask    = maskN(bits);
      long long valA    = strtoll(paramA.c_str(), NULL, 2) & mask;
      long long valB    = strtoll(paramB.c_str(), NULL, 2) & mask;
      long long signedA = twos_to_int(valA, bits);
      long long signedB = twos_to_int(valB, bits);

      // intervalo representável em complemento de dois com 'bits' bits
      long long minVal = -(1LL << (bits - 1));
      long long maxVal = (1LL << (bits - 1)) - 1LL;

      long long resultadoFull = 0;
      bool overflow = false;

      if (op == "add") {
        resultadoFull = signedA + signedB;
        long long s = twos_to_int(resultadoFull & mask, bits);
        // overflow de soma: operandos de mesmo sinal e resultado de sinal oposto
        overflow = (signedA < 0) == (signedB < 0) && (signedA < 0) != (s < 0);
      } else if (op == "sub") {
        resultadoFull = signedA - signedB;
        long long s = twos_to_int(resultadoFull & mask, bits);
        // subtracao = soma com -B; usa o sinal efetivo de -B
        long long efB = -signedB;
        overflow = (signedA < 0) == (efB < 0) && (signedA < 0) != (s < 0);
      } else if (op == "mult") {
        resultadoFull = signedA * signedB;
        // overflow se o produto real nao couber no intervalo
        overflow = (resultadoFull < minVal) || (resultadoFull > maxVal);
      } else if (op == "fact") {
        // fatorial de A; ignora B. Definido apenas para A >= 0.
        if (signedA < 0) {
          if (bits == 4) escreverLEDs(0);
          request->send(200, "text/plain",
                        "A=" + to_bin(valA, bits) + " (" + String(signedA) + ")\n"
                        "BITS=" + String(bits) + "\n"
                        "OP=fact\nERRO=fatorial nao definido para negativos");
          return;
        }
        long long fat = 1;
        for (long long i = 2; i <= signedA; i++) {
          fat *= i;
          if (fat > maxVal) { overflow = true; } // já estourou, mas continua só p/ valor truncado
        }
        resultadoFull = fat;
        // overflow se o fatorial real nao couber no intervalo
        overflow = overflow || (fat < minVal) || (fat > maxVal);
      } else {
        request->send(400, "text/plain", "Operacao invalida");
        return;
      }

      long long resultado    = resultadoFull & mask;
      long long resultadoSigned = twos_to_int(resultado, bits);

      // Hardware: LEDs apenas no modo 4 bits; nos demais, apaga os LEDs.
      if (bits == 4) {
        escreverLEDs((int)(resultado & 0x0F));
      } else {
        escreverLEDs(0);
      }

      // Resposta formatada
      String body = "A=" + to_bin(valA, bits) + " (" + String(signedA) + ")\n";
      if (op == "fact") {
        body += "B=(ignorado)\n";
      } else {
        body += "B=" + to_bin(valB, bits) + " (" + String(signedB) + ")\n";
      }
      body += "BITS=" + String(bits) + "\n";
      body += "OP=" + op + "\n";
      body += "RES=" + to_bin(resultado, bits) + " (" + String(resultadoSigned) + ")\n";
      body += "OVERFLOW=" + String(overflow ? 1 : 0);

      request->send(200, "text/plain", body);
    } else {
      request->send(400, "text/plain", "Faltam parametros");
    }
  });

  server.begin();
}

void loop() {}
