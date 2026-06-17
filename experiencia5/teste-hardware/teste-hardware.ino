const int PIN_BTN = 5;
const int PIN_LED = 6;

void setup() {
  Serial.begin(115200);

  pinMode(PIN_BTN, INPUT_PULLUP);
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LOW);

  Serial.println("Etapa 2 - teste de hardware (botao + LED) iniciado.");
}

void loop() {
  bool pressionado = (digitalRead(PIN_BTN) == LOW);

  digitalWrite(PIN_LED, pressionado ? LOW : HIGH);

  static bool anterior = false;
  static bool primeira = true;
  if (primeira || pressionado != anterior) {
    primeira = false;
    anterior = pressionado;
    Serial.printf("botao=%s  ->  LED=%s\n",
                  pressionado ? "PRESSIONADO" : "solto",
                  pressionado ? "ON" : "off");
  }

  delay(10);
}
