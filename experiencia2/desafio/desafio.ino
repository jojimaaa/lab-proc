void setup() {
  Serial.begin(9600);
  delay(1000); // Tempo para abrir o monitor serial

  Serial.println("\n==========================================");
  Serial.println("   CALCULADORA 4-BIT: COMPLEMENTO DE 1  ");
  Serial.println("==========================================");
  Serial.println("Digite no formato: BBBB op BBBB");
  Serial.println("Exemplo: 0101 + 0010  ou  0011 - 0001");
  Serial.println("------------------------------------------");
}

// Converte binário de 4 bits (C1) para inteiro com sinal
int ones4_to_int(int v4) {
  v4 &= 0x0F;
  if (v4 & 0x08) { // Bit de sinal (MSB) é 1?
    return -(~v4 & 0x0F); // Inverte e nega
  }
  return v4;
}

// Formata para exibição binária com 4 casas
String printBin4(int v4) {
  String s = "";
  for (int i = 3; i >= 0; i--) {
    s += ((v4 >> i) & 1) ? '1' : '0';
  }
  return s;
}

void loop() {
  if (Serial.available() > 0) {
    String entrada = Serial.readStringUntil('\n');
    entrada.trim();

    if (entrada.length() < 11) return;

    // Parsing
    String strA = entrada.substring(0, 4);
    char op = entrada.charAt(5);
    String strB = entrada.substring(7, 11);

    int valA = (int)strtol(strA.c_str(), NULL, 2) & 0x0F;
    int valB = (int)strtol(strB.c_str(), NULL, 2) & 0x0F;

    // Para detecção de overflow, precisamos saber os sinais ANTES da operação
    // No Complemento de 1, o sinal é o MSB (bit 3)
    bool sinalA = (valA & 0x08); 
    
    int operandoB;
    if (op == '-') {
      operandoB = (~valB) & 0x0F;
    } else {
      operandoB = valB;
    }
    bool sinalB = (operandoB & 0x08); // Sinal do segundo operando (já invertido se for sub)

    // Soma com End-Around Carry
    int somaTotal = valA + operandoB;
    int resultado4;

    if (somaTotal > 0x0F) {
      resultado4 = (somaTotal & 0x0F) + 1;
    } else {
      resultado4 = somaTotal & 0x0F;
    }

    // --- Lógica de Overflow ---
    bool sinalRes = (resultado4 & 0x08);
    // Overflow: Sinais de entrada iguais, mas sinal do resultado diferente
    bool overflow = (sinalA == sinalB) && (sinalA != sinalRes);

    // Exibição
    Serial.println("\n> OPERAÇÃO: " + strA + " " + op + " " + strB);
    Serial.println("------------------------------------------");
    Serial.print("RESULTADO BINARIO: ");
    Serial.println(printBin4(resultado4));
    
    Serial.print("RESULTADO DECIMAL: ");
    Serial.println(ones4_to_int(resultado4));

    if (overflow) {
      Serial.println("⚠️ [ALERTA] OVERFLOW DETECTADO!");
      Serial.println("   O resultado excedeu a faixa de -7 a +7.");
    } else {
      Serial.println("✅ [OK] Resultado dentro da faixa.");
    }

    // Verificação de Zero Negativo
    if (resultado4 == 0x0F) Serial.println("[NOTA] Representação: Zero Negativo (1111)");
    
    Serial.println("------------------------------------------");
  }
}