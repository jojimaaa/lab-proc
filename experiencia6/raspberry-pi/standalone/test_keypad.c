/*
 * test_keypad.c - Testa/diagnostica o teclado matricial 4x4 ISOLADO (sem LCD).
 * VERSAO PULL-DOWN (ativo-alto): linhas em repouso LOW, acionadas em HIGH;
 * colunas com pull-down (repouso = 0), toque leva a coluna a 1.
 *
 *   Compila: gcc test_keypad.c -lwiringPi -o test_keypad
 *   Roda:    sudo ./test_keypad        (Ctrl+C para sair)
 *
 * Diagnostico de repouso (pull-down): cada coluna DEVE ler 0. Se alguma ler 1,
 * o pull-down daquela coluna nao pegou (ex.: GPIO5/6 nascem em pull-up) -> veja
 * o README (fixar pull-down no /boot/firmware/config.txt).
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

/* varre a matriz uma vez; devolve 1 se achou tecla (r,c preenchidos) */
static int scan(int *pr, int *pc) {
    for (int r = 0; r < 4; r++) {
        digitalWrite(ROWS[r], HIGH);
        delayMicroseconds(50);              /* deixa a linha estabilizar */
        for (int c = 0; c < 4; c++) {
            if (digitalRead(COLS[c]) == HIGH) {
                digitalWrite(ROWS[r], LOW);
                *pr = r; *pc = c;
                return 1;
            }
        }
        digitalWrite(ROWS[r], LOW);
    }
    return 0;
}

int main(void) {
    if (wiringPiSetupGpio() < 0) {
        fprintf(stderr, "wiringPi falhou (rode com sudo).\n");
        return 1;
    }
    for (int i = 0; i < 4; i++) {
        pinMode(ROWS[i], OUTPUT);
        digitalWrite(ROWS[i], LOW);         /* repouso das linhas = LOW */
        pinMode(COLS[i], INPUT);
        pullUpDnControl(COLS[i], PUD_DOWN); /* colunas em pull-down     */
    }
    delay(50);

    /* ---- diagnostico de repouso (nenhuma tecla) : colunas devem ler 0 ---- */
    printf("== Diagnostico (NAO aperte nada agora) ==\n");
    int suspeita = 0;
    for (int c = 0; c < 4; c++) {
        int v = digitalRead(COLS[c]);
        printf("  coluna %d (GPIO%2d) em repouso = %d %s\n",
               c, COLS[c], v, v == 1 ? "  <-- DEVERIA SER 0! (pull-down nao pegou)" : "");
        if (v == 1) suspeita = 1;
    }
    if (suspeita)
        printf("\n>> Alguma coluna leu 1 sem tecla: pull-down nao ativo nela.\n"
               ">> Fixe pull-down no /boot/firmware/config.txt (veja o README).\n\n");
    else
        printf("\n>> Repouso OK (tudo em 0). Agora pressione teclas:\n\n");

    /* ---- scan sem spam (uma impressao por tecla) ---- */
    for (;;) {
        int r, c;
        if (scan(&r, &c)) {
            printf("linha=%d (GPIO%d)  coluna=%d (GPIO%d)  ->  '%c'\n",
                   r, ROWS[r], c, COLS[c], KEYS[r][c]);
            while (scan(&r, &c)) delay(10);   /* espera soltar */
        }
        delay(20);
    }
    return 0;
}
