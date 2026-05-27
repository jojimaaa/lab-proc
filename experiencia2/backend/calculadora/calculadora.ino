// =====================================================================
// Calculadora Binaria 4 bits - Back-end no ESP32-C3
//
// Endpoint:  GET /calc?a=BBBB&b=BBBB&op=add|sub
//   a, b : strings binarias de ate 4 bits (ex.: "0110")
//   op   : "add" (soma) ou "sub" (subtracao)
//
// Resposta (texto simples):
//   A=0101 (+5)
//   B=0100 (+4)
//   OP=add
//   RES=1001 (-7)        <- em complemento de dois, 4 bits
//   OVERFLOW=1           <- 0 = OK, 1 = estourou
//
// Os 4 bits do resultado sao espelhados em GPIOs (LEDs).
// Bit 3 (MSB) e o bit de SINAL no complemento de dois.
// =====================================================================

#include <WiFi.h>
#include <WebServer.h>

// --------- Wi-Fi: modo Access Point (a placa cria a rede) -------------
// Conecte o celular/notebook em "ESP32-CALC" (senha 12345678)
// e abra http://192.168.4.1/calc?... no navegador (mesmo IP usado no front).
const char* AP_SSID = "ESP32-CALC";
const char* AP_PASS = "12345678";

// --------- Mapeamento dos LEDs de saida (4 bits) ----------------------
// Ajuste os pinos conforme a sua montagem. No ESP32-C3 os GPIOs 2,3,4,5
// sao livres e proximos uns dos outros.
const int LED_BIT0 = 2;  // LSB - bit 0 (peso 1)
const int LED_BIT1 = 3;  //       bit 1 (peso 2)
const int LED_BIT2 = 4;  //       bit 2 (peso 4)
const int LED_BIT3 = 5;  // MSB - bit 3 (bit de SINAL no comp. de dois)

WebServer server(80);

// ---------------------------------------------------------------------
// Converte 4 bits "crus" (0..15) para inteiro com sinal em comp. de dois
// (faixa: -8 a +7). Se o bit 3 estiver setado, e negativo.
// ---------------------------------------------------------------------
int twos4_to_int(int v4) {
  v4 &= 0x0F;
  return (v4 & 0x08) ? (v4 - 16) : v4;
}

// Formata um inteiro de 4 bits como string binaria "bbbb"
String to_bin4(int v4) {
  v4 &= 0x0F;
  String s = "";
  for (int i = 3; i >= 0; i--) s += ((v4 >> i) & 1) ? '1' : '0';
  return s;
}

// Escreve os 4 bits do resultado nos LEDs
void escreverLEDs(int v4) {
  v4 &= 0x0F;  // mascara: garante 4 bits
  digitalWrite(LED_BIT0, (v4 >> 0) & 0x01);
  digitalWrite(LED_BIT1, (v4 >> 1) & 0x01);
  digitalWrite(LED_BIT2, (v4 >> 2) & 0x01);
  digitalWrite(LED_BIT3, (v4 >> 3) & 0x01);
}

// ---------------------------------------------------------------------
// Handler do endpoint /calc
// ---------------------------------------------------------------------
void handleCalc() {
  // CORS para o front (file:// ou outro host) conseguir ler a resposta
  server.sendHeader("Access-Control-Allow-Origin", "*");

  if (!server.hasArg("a") || !server.hasArg("b") || !server.hasArg("op")) {
    server.send(400, "text/plain", "Faltam parametros: a, b, op");
    return;
  }

  String paramA = server.arg("a");
  String paramB = server.arg("b");
  String op     = server.arg("op");

  // 1) Parsing: string binaria -> inteiro (base 2)
  //    strtol aceita ate 4 chars "0"/"1"; depois mascaramos para 4 bits.
  int rawA = (int) strtol(paramA.c_str(), NULL, 2);
  int rawB = (int) strtol(paramB.c_str(), NULL, 2);
  int valA4 = rawA & 0x0F;
  int valB4 = rawB & 0x0F;

  // Interpretacao como complemento de dois (4 bits)
  int signedA = twos4_to_int(valA4);
  int signedB = twos4_to_int(valB4);

  // 2) Operacao aritmetica nativa em C
  int resultadoFull;       // resultado "largo" (sem mascara) p/ detectar overflow
  int operandoB_efetivo;   // B para soma, -B para subtracao (usado na regra de sinal)

  if (op == "add") {
    resultadoFull   = signedA + signedB;
    operandoB_efetivo = signedB;
  } else if (op == "sub") {
    resultadoFull   = signedA - signedB;
    operandoB_efetivo = -signedB;
  } else {
    server.send(400, "text/plain", "op deve ser add ou sub");
    return;
  }

  // 3) Mascaramento: garante 4 bits (o que de fato apareceria no hardware)
  int resultado4 = resultadoFull & 0x0F;
  int resultadoSigned = twos4_to_int(resultado4);

  // ---- Deteccao de OVERFLOW em complemento de dois ----
  // Regra classica: overflow ocorre quando os dois operandos tem o MESMO
  // sinal e o resultado (em 4 bits) tem sinal DIFERENTE deles.
  //   (+) + (+) = (-)  -> overflow
  //   (-) + (-) = (+)  -> overflow
  // Para subtracao, aplicamos a mesma regra usando -B no lugar de B.
  bool sinalA = (signedA          < 0);
  bool sinalB = (operandoB_efetivo < 0);
  bool sinalR = (resultadoSigned  < 0);
  bool overflow = (sinalA == sinalB) && (sinalA != sinalR);

  // 4) Saida para os GPIOs (LEDs) - sempre escreve os 4 bits mascarados
  escreverLEDs(resultado4);

  // ---- Monta resposta em texto simples ----
  String body;
  body += "A=" + to_bin4(valA4) + " (" + String(signedA) + ")\n";
  body += "B=" + to_bin4(valB4) + " (" + String(signedB) + ")\n";
  body += "OP=" + op + "\n";
  body += "RES=" + to_bin4(resultado4) + " (" + String(resultadoSigned) + ")\n";
  body += "OVERFLOW=" + String(overflow ? 1 : 0) + "\n";

  // Se quiser sinalizar overflow tambem no HTTP, da pra usar 409:
  // int status = overflow ? 409 : 200;
  server.send(200, "text/plain", body);
}

// Pre-flight CORS (alguns browsers mandam OPTIONS antes do GET)
void handleOptions() {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  server.send(204);
}

void setup() {
  Serial.begin(115200);

  pinMode(LED_BIT0, OUTPUT);
  pinMode(LED_BIT1, OUTPUT);
  pinMode(LED_BIT2, OUTPUT);
  pinMode(LED_BIT3, OUTPUT);
  escreverLEDs(0);

  // Sobe um Access Point proprio (IP fixo 192.168.4.1)
  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_SSID, AP_PASS);
  Serial.print("AP IP: ");
  Serial.println(WiFi.softAPIP());  // deve imprimir 192.168.4.1

  server.on("/calc", HTTP_GET,     handleCalc);
  server.on("/calc", HTTP_OPTIONS, handleOptions);
  server.begin();
  Serial.println("HTTP server iniciado em /calc");
}

void loop() {
  server.handleClient();
}
