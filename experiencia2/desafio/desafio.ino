#include <Arduino.h>
#include <WiFi.h>
#include <NetworkClient.h>
#include <WiFiAP.h>

// Pinos dos LEDs no ESP32
// TROCAR OS PINOS PARA PINOS USUAIS NO ESP32
const int LED_BIT3 = 5;
const int LED_BIT2 = 6;
const int LED_BIT1 = 7;
const int LED_BIT0 = 8;

// Nome da rede no wifi
const char *ssid = "Calc_Blaster_Master";

NetworkServer server(80);

// HTML com JS embutido (MODIFICADO PARA INCLUIR BENCHMARK)
const char *html_page = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Calculadora Binaria</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        button { margin: 5px; padding: 10px; cursor: pointer; }
        .btn-bench { background-color: #ff9800; color: white; font-weight: bold; border: none; border-radius: 4px; }
        .btn-excel { background-color: #4CAF50; color: white; font-weight: bold; border: none; border-radius: 4px; margin-top: 10px;}
        .resultado-box { margin-top: 20px; padding: 15px; border: 1px solid #ccc; background: #f9f9f9; }
        
        #benchmark-section { margin-top: 30px; display: none; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 14px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <h2>Calculadora Multi-bits ESP32</h2>
    <p>Insira os valores em binário (o tamanho do bit ditará o sinal em complemento de 2):</p>
    Operando A: <input type="text" id="valA" value="00000110"><br><br>
    Operando B: <input type="text" id="valB" value="00000010"><br><br>
    
    <button onclick="calcular('add')">SOMA (+)</button>
    <button onclick="calcular('sub')">SUBTRAÇÃO (-)</button>
    <button onclick="calcular('mul')">MULTIPLICAÇÃO (*)</button>
    <button onclick="calcular('div')">DIVISÃO (/)</button>
    <button onclick="calcular('fat')">FATORIAL de A (!)</button>
    <hr>
    <button class="btn-bench" onclick="runBenchmark()">🚀 RODAR BENCHMARK (Relatório)</button>
    <br><br>
    
    <div class="resultado-box">
        <b>Resultado:</b>
        <p id="resultado">Aguardando operação...</p>
    </div>

    <div id="benchmark-section">
        <h3>Resultados do Benchmark</h3>
        <p id="bench-status" style="color: blue;">Processando testes... Aguarde.</p>
        <table id="benchTable">
            <thead>
                <tr>
                    <th>Operação</th>
                    <th>Tamanho (A / B)</th>
                    <th>T1 (&mu;s)</th>
                    <th>T2 (&mu;s)</th>
                    <th>T3 (&mu;s)</th>
                    <th>T4 (&mu;s)</th>
                    <th>T5 (&mu;s)</th>
                    <th>Média (&mu;s)</th>
                    <th>Desvio Padrão</th>
                </tr>
            </thead>
            <tbody id="benchBody"></tbody>
        </table>
        <button class="btn-excel" onclick="downloadCSV()">⬇️ Baixar Tabela em Excel (CSV)</button>
    </div>
    
    <script>
        function calcular(op) {
            let a = document.getElementById('valA').value;
            let b = document.getElementById('valB').value;
            if(!a) a = "0";
            if(!b) b = "0";
            
            document.getElementById('resultado').innerHTML = "Calculando...";
            
            fetch(`/calc?a=${a}&b=${b}&op=${op}`)
                .then(response => response.text())
                .then(data => {
                    document.getElementById('resultado').innerHTML = data;
                });
        }

        // --- LÓGICA DO BENCHMARK ---
        const testCases = [
            // MULTIPLICAÇÃO (diferentes tamanhos de bits)
            { op: 'mul', a: '0111', b: '0011', desc: 'Mul 4-bits' }, // 7 * 3
            { op: 'mul', a: '01111111', b: '01111111', desc: 'Mul 8-bits' }, // 127 * 15
            { op: 'mul', a: '0111111111111111', b: '0111111111111111', desc: 'Mul 16-bits' }, // 32767 * 255
            { op: 'mul', a: '01111111111111111111111111111111', b: '01111111111111111111111111111111', desc: 'Mul 32-bits' }, // (Max) * 65535
            // FATORIAL (crescimento do operando A)
{ op: 'fat', a: '0111', b: '0', desc: 'Fat (7!)' },					// 3 bits de '1' = 7
            { op: 'fat', a: '0111111', b: '0', desc: 'Fat (63!)' },					// 6 bits de '1' = 63
            { op: 'fat', a: '0111111111111', b: '0', desc: 'Fat (4095!)' },			// 12 bits de '1' = 4095
            { op: 'fat', a: '0111111111111111', b: '0', desc: 'Fat (32767!)' },		// 15 bits de '1' = 32767
            { op: 'fat', a: '01111111111111111111', b: '0', desc: 'Fat (524287!)' },
              // DIVISÃO (Desafio: Diferentes tamanhos de operandos)
            { op: 'div', a: '0111', b: '0010', desc: 'Div 4-bits (7 / 2)' },
            { op: 'div', a: '01111111', b: '00000100', desc: 'Div 8-bits (127 / 4)' },
            { op: 'div', a: '0111111111111111', b: '0000000010000000', desc: 'Div 16-bits (32767 / 128)' },
            { op: 'div', a: '01111111111111111111111111111111', b: '00000000010000000000000000000000', desc: 'Div 32-bits (Max / 4194304)' }
        ];

        async function runBenchmark() {
            document.getElementById('benchmark-section').style.display = 'block';
            let tbody = document.getElementById('benchBody');
            tbody.innerHTML = ''; // limpa tabela anterior
            document.getElementById('bench-status').innerText = "Processando testes... Aguarde.";

            for (let tc of testCases) {
                let times = [];
                for(let i = 0; i < 5; i++) {
                    let res = await fetch(`/calc?a=${tc.a}&b=${tc.b}&op=${tc.op}`);
                    let text = await res.text();
                    
                    // Extrai o tempo da string HTML usando Regex
                    let match = text.match(/Tempo de processamento \(C no ESP32\): <b>(\d+)/);
                    if(match && match[1]) {
                        times.push(parseInt(match[1]));
                    } else {
                        times.push(0); // Em caso de erro na extração
                    }
                }

                // Cálculo de Média e Desvio Padrão
                let sum = times.reduce((acc, val) => acc + val, 0);
                let avg = sum / 5;
                let variance = times.reduce((acc, val) => acc + Math.pow(val - avg, 2), 0) / 5;
                let stddev = Math.sqrt(variance);

                // Adiciona linha na tabela
                let tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${tc.desc}</td>
                    <td>A: ${tc.a.length} bits<br>B: ${tc.b.length} bits</td>
                    <td>${times[0]}</td>
                    <td>${times[1]}</td>
                    <td>${times[2]}</td>
                    <td>${times[3]}</td>
                    <td>${times[4]}</td>
                    <td><b>${avg.toFixed(2)}</b></td>
                    <td>${stddev.toFixed(2)}</td>
                `;
                tbody.appendChild(tr);
            }
            document.getElementById('bench-status').innerText = "✅ Benchmark finalizado!";
        }

        // Exportação para Excel (CSV)
        function downloadCSV() {
            let csv = [];
            let rows = document.querySelectorAll("table tr");
            
            for (let i = 0; i < rows.length; i++) {
                let row = [], cols = rows[i].querySelectorAll("td, th");
                
                for (let j = 0; j < cols.length; j++) 
                    // Limpa quebras de linha e vírgulas para não quebrar o CSV
                    row.push('"' + cols[j].innerText.replace(/(\r\n|\n|\r)/gm, " ") + '"');
                
                csv.push(row.join(";")); // Usando ponto e vírgula para abrir bem no Excel PT-BR
            }

            let csvFile = new Blob(["\uFEFF" + csv.join("\n")], {type: "text/csv;charset=utf-8;"});
            let downloadLink = document.createElement("a");
            downloadLink.download = "Benchmark_ESP32.csv";
            downloadLink.href = window.URL.createObjectURL(csvFile);
            downloadLink.style.display = "none";
            document.body.appendChild(downloadLink);
            downloadLink.click();
            document.body.removeChild(downloadLink);
        }
    </script>
</body>
</html>
)rawliteral";

// Função para interpretar binário de tamanho dinâmico (Complemento de 2)
long parseBinarySigned(String binStr)
{
    long val = strtol(binStr.c_str(), NULL, 2);
    int len = binStr.length();
    // Se o bit mais significativo for 1, o número é negativo
    if (len > 0 && binStr.charAt(0) == '1')
    {
        val -= (1 << len);
    }
    return val;
}

void setup()
{
    pinMode(LED_BIT3, OUTPUT);
    pinMode(LED_BIT2, OUTPUT);
    pinMode(LED_BIT1, OUTPUT);
    pinMode(LED_BIT0, OUTPUT);

    Serial.begin(115200);
    Serial.println("Configurando access point...");

    if (!WiFi.softAP(ssid))
    {
        log_e("Soft AP creation failed.");
        while (1)
            ;
    }

    IPAddress myIP = WiFi.softAPIP();
    Serial.print("AP IP address: ");
    Serial.println(myIP);

    server.begin();
    Serial.println("Server started");
}

void loop()
{
    NetworkClient client = server.accept();

    if (client)
    {
        String currentLine = "";
        String header = "";

        while (client.connected())
        {
            if (client.available())
            {
                char c = client.read();
                header += c;

                if (c == '\n')
                {
                    if (currentLine.length() == 0)
                    {
                        client.println("HTTP/1.1 200 OK");
                        client.println("Content-type:text/html; charset=UTF-8");
                        client.println();

                        if (header.indexOf("GET /calc") >= 0)
                        {
                            int a_idx = header.indexOf("a=");
                            int b_idx = header.indexOf("&b=");
                            int op_idx = header.indexOf("&op=");
                            int fim_idx = header.indexOf(" HTTP");

                            String paramA = header.substring(a_idx + 2, b_idx);
                            String paramB = header.substring(b_idx + 3, op_idx);
                            String op = header.substring(op_idx + 4, fim_idx);

                            long valA = parseBinarySigned(paramA);
                            long valB = parseBinarySigned(paramB);
                            long res_decimal = 0;

                            bool erro = false;
                            String msg_erro = "";

                            // INICIO DE MEDIÇÃO DE TEMPO REQUISITO 6
                            unsigned long t_start = micros();

                            if (op == "add")
                            {
                                res_decimal = valA + valB;
                            }
                            else if (op == "sub")
                            {
                                res_decimal = valA - valB;
                            }
                            else if (op == "mul")
                            {
                                // REQUISITO 3 e 5: Multiplicação
                                long a = abs(valA);
                                long b = abs(valB);
                                res_decimal = 0;
                                // Critério de parada: quando o multiplicador (b) for zero
                                while (b > 0)
                                {
                                    if (b & 1)
                                        res_decimal += a;
                                    a <<= 1;
                                    b >>= 1;
                                }
                                if ((valA < 0 && valB > 0) || (valA > 0 && valB < 0))
                                {
                                    res_decimal = -res_decimal;
                                }
                            }
                            else if (op == "fat")
                            {
                                // REQUISITO 4 e 5: Fatorial
                                if (valA < 0)
                                {
                                    erro = true;
                                    msg_erro = "Fatorial não definido para negativos.";
                                }
                                else
                                {
                                    res_decimal = 1;
                                    // condicao para parada
                                    for (long i = 1; i <= valA; i++)
                                    {
                                        res_decimal *= i;
                                    }
                                }
                            }
                            else if (op == "div")
                            {
                                // REQUISITO 7 (Desafio): Divisão por subtrações sucessivas
                                if (valB == 0)
                                {
                                    erro = true;
                                    msg_erro = "Divisão por Zero!";
                                }
                                else
                                {
                                    long a = abs(valA);
                                    long b = abs(valB);
                                    res_decimal = 0;
                                    // Critério de parada: dividendo menor que o divisor
                                    while (a >= b)
                                    {
                                        a -= b;
                                        res_decimal++;
                                    }
                                    if ((valA < 0 && valB > 0) || (valA > 0 && valB < 0))
                                    {
                                        res_decimal = -res_decimal;
                                    }
                                }
                            }

                            // FIM DO CALCULO DE TEMPO
                            unsigned long t_end = micros();
                            unsigned long tempo_exec = t_end - t_start;

                            // Atualização dos LEDs (mantém o Requisito 1 e 2 - Mostra apenas os 4 LSBs)
                            int saida_leds = res_decimal & 0x0F;
                            digitalWrite(LED_BIT0, saida_leds & 0x01);
                            digitalWrite(LED_BIT1, (saida_leds >> 1) & 0x01);
                            digitalWrite(LED_BIT2, (saida_leds >> 2) & 0x01);
                            digitalWrite(LED_BIT3, (saida_leds >> 3) & 0x01);

                            // Respostas do front end
                            if (erro)
                            {
                                client.print("<span style='color:red; font-weight:bold;'>" + msg_erro + "</span>");
                            }
                            else
                            {
                                client.print("Valor Decimal: <b>" + String(res_decimal) + "</b><br>");
                                client.print("Binário Bruto (ESP32): <b>" + String(res_decimal, BIN) + "</b><br><br>");
                                client.print("<span style='color:blue;'>Tempo de processamento (C no ESP32): <b>" + String(tempo_exec) + " microssegundos (&mu;s)</b></span>");
                            }
                        }
                        else
                        {
                            client.print(html_page);
                        }

                        client.println();
                        break;
                    }
                    else
                    {
                        currentLine = "";
                    }
                }
                else if (c != '\r')
                {
                    currentLine += c;
                }
            }
        }
        client.stop();
    }
}