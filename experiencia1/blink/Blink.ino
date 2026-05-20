int T = 200; // Diferentes intervalos: 1000, 200, 50 ms 

void setup() {
  // initialize digital pin LED_BUILTIN as an output.
  pinMode(LED_BUILTIN, OUTPUT);
}

void loop() {
  digitalWrite(LED_BUILTIN, HIGH);  // turn the LED on
  delay(T);
  digitalWrite(LED_BUILTIN, LOW);   // turn the LED off
  delay(T);                         
}
