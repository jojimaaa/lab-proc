#include <WiFi.h>
#include <WebServer.h>

// config de rede (O ESP32 vai CRIAR esta rede)
const char *ssid = "ManipuladorDeAlmas";
const char *password = "12121600"; // Senha precisa ter no mínimo 8 caracteres!

WebServer server(80);

// mapeamento dos pinos (verificar pinout da placa)
const int ledPin = 3;
const int servoPin = 4;

// Configurações PWM (Nova API v3.0+)
int ledFreq = 1000;          // Inicial em 1 kHz
const int ledResolution = 8; // 8 bits (0 a 255)

const int servoFreq = 50;       // 50Hz = período de 20ms
const int servoResolution = 12; // 12 bits (0 a 4095) para maior precisão

// interface web
const char index_html[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Painel ESP32-C3 - Lab 5</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; background-color: #eef2f5; padding: 15px; margin: 0; }
        .container { max-width: 450px; margin: auto; background: white; padding: 25px; border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
        h2 { color: #2c3e50; margin-bottom: 25px; }
        .slider-group { margin: 20px 0; text-align: left; background: #f8f9fa; padding: 15px; border-radius: 8px; border: 1px solid #ddd; }
        label { font-weight: bold; color: #34495e; font-size: 1.1em; }
        input[type=range] { width: 100%; margin-top: 15px; cursor: pointer; height: 8px; background: #bdc3c7; border-radius: 5px; outline: none; }
        span.val { color: #e74c3c; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Controle de Periféricos</h2>
        
        <div class="slider-group">
            <label>Brilho do LED: <span id="ledVal" class="val">0</span>%</label>
            <input type="range" id="ledSlider" min="0" max="100" value="0" oninput="updateESP()">
        </div>

        <div class="slider-group">
            <label>Frequência (LED): <span id="freqVal" class="val">1000</span> Hz</label>
            <input type="range" id="freqSlider" min="50" max="5000" step="50" value="1000" oninput="updateESP()">
        </div>

        <div class="slider-group">
            <label>Posição do Servo: <span id="servoVal" class="val">0</span>&deg;</label>
            <input type="range" id="servoSlider" min="0" max="180" value="0" oninput="updateESP()">
        </div>
    </div>

    <script>
        function updateESP() {
            let led = document.getElementById("ledSlider").value;
            let freq = document.getElementById("freqSlider").value;
            let servo = document.getElementById("servoSlider").value;

            document.getElementById("ledVal").innerText = led;
            document.getElementById("freqVal").innerText = freq;
            document.getElementById("servoVal").innerText = servo;

            fetch(`/api/update?led=${led}&freq=${freq}&servo=${servo}`);
        }
    </script>
</body>
</html>
)rawliteral";

// requisicoes para alteracao
void handleUpdate()
{
    if (server.hasArg("led") && server.hasArg("freq") && server.hasArg("servo"))
    {
        int ledPercent = server.arg("led").toInt();
        int newFreq = server.arg("freq").toInt();
        int servoAngle = server.arg("servo").toInt();

        if (newFreq != ledFreq)
        {
            ledFreq = newFreq;
            ledcAttach(ledPin, ledFreq, ledResolution);
        }

        int ledDuty = map(ledPercent, 0, 100, 0, 255);
        ledcWrite(ledPin, ledDuty);

        int servoDuty = map(servoAngle, 0, 180, 205, 410);
        ledcWrite(servoPin, servoDuty);

        server.send(200, "text/plain", "OK");
    }
    else
    {
        server.send(400, "text/plain", "Bad Request");
    }
}

void setup()
{
    Serial.begin(115200);
    delay(100);

    // Configuração do hardware PWM
    ledcAttach(ledPin, ledFreq, ledResolution);
    ledcAttach(servoPin, servoFreq, servoResolution);

    ledcWrite(ledPin, 0);
    ledcWrite(servoPin, map(0, 0, 180, 205, 410));

    // MODIFICAÇÃO AQUI: Configurando o ESP32 como Ponto de Acesso (Access Point)
    Serial.println("\nIniciando Ponto de Acesso (AP)...");
    WiFi.softAP(ssid, password);

    Serial.println("Rede Wi-Fi criada com sucesso!");
    Serial.print("Nome da Rede (SSID): ");
    Serial.println(ssid);
    
    // Em modo AP, o IP padrão do ESP32 costuma ser sempre 192.168.4.1
    Serial.print("Acesse o painel no navegador via IP: ");
    Serial.println(WiFi.softAPIP()); 

    // roteamento de uris do servidor
    server.on("/", []() { 
        server.send(200, "text/html", index_html); 
    });
    server.on("/api/update", handleUpdate);

    server.begin();
}

void loop()
{
    server.handleClient();
}