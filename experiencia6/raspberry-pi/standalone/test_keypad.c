/*
 * test_keypad.c - Testa o teclado matricial 4x4 ISOLADO (sem LCD).
 * Imprime, a cada tecla, o indice de linha/coluna e a tecla mapeada -- util
 * para descobrir se os pinos e a orientacao da matriz KEYS estao corretos.
 *
 *   Compila: gcc test_keypad.c -lwiringPi -o test_keypad
 *   Roda:    sudo ./test_keypad        (Ctrl+C para sair)
 *
 * Se a DETECCAO nao acontece -> pinos errados (confira ROWS/COLS).
 * Se detecta mas a TECLA impressa nao bate com a fisica -> troque a orientacao
 * (inverta ROWS<->COLS, ou reordene, ou ajuste a matriz KEYS).
 */
#include <stdio.h>
#include <wiringPi.h>

static const int ROWS[4] = {16, 20, 21, 26};   /* BCM, saidas   */
static const int COLS[4] = {19, 13, 6, 5};     /* BCM, entradas */
static const char KEYS[4][4] = {
    {'1', '2', '3', 'A'},
    {'4', '5', '6', 'B'},
    {'7', '8', '9', 'C'},
    {'*', '0', '#', 'D'},
};

int main(void) {
    if (wiringPiSetupGpio() < 0) {
        fprintf(stderr, "wiringPi falhou (rode com sudo).\n");
        return 1;
    }
    for (int i = 0; i < 4; i++) {
        pinMode(ROWS[i], OUTPUT);
        digitalWrite(ROWS[i], HIGH);
        pinMode(COLS[i], INPUT);
        pullUpDnControl(COLS[i], PUD_UP);
    }

    printf("Pressione teclas (Ctrl+C para sair)...\n");
    for (;;) {
        for (int r = 0; r < 4; r++) {
            digitalWrite(ROWS[r], LOW);
            for (int c = 0; c < 4; c++) {
                if (digitalRead(COLS[c]) == LOW) {
                    printf("linha=%d (GPIO%d)  coluna=%d (GPIO%d)  ->  tecla '%c'\n",
                           r, ROWS[r], c, COLS[c], KEYS[r][c]);
                    delay(300);          /* debounce simples */
                }
            }
            digitalWrite(ROWS[r], HIGH);
        }
        delay(20);
    }
    return 0;
}
