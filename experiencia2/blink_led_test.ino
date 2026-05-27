// Definição dos pinos que serão testados
const int pinosLeds[] = {4, 5, 6, 7};
const int numLeds = 4;

void setup() {
  // Configura todos os pinos como saída
  for (int i = 0; i < numLeds; i++) {
    pinMode(pinosLeds[i], OUTPUT);
  }
}

void loop() {
  // Percorre cada LED da lista
  for (int i = 0; i < numLeds; i++) {
    digitalWrite(pinosLeds[i], HIGH); // Liga o LED
    delay(200);                        // Espera 200ms
    digitalWrite(pinosLeds[i], LOW);  // Desliga o LED
  }
  
  // Pequena pausa antes de reiniciar a sequência
  delay(500);
}