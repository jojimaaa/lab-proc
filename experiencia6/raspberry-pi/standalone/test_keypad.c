/*
 * test_keypad.c - Testa/diagnostica o teclado matricial 4x4 ISOLADO (sem LCD).
 *
 *   Compila: gcc test_keypad.c -lwiringPi -o test_keypad
 *   Roda:    sudo ./test_keypad        (Ctrl+C para sair)
 *
 * Faz duas coisas:
 *  1) DIAGNOSTICO de repouso: sem nenhuma tecla, cada coluna DEVE ler 1 (HIGH),
 *     por causa do pull-up interno. Se alguma ler 0, o pull-up nao esta ativo
 *     ou ha fio solto/curto -> e por isso que "printa adoidado".
 *  2) SCAN: imprime UMA vez por tecla (espera soltar), mostrando linha/coluna
 *     e a tecla mapeada -- serve pra conferir a orientacao da matriz KEYS.
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
        digitalWrite(ROWS[r], LOW);
        delayMicroseconds(50);              /* deixa a linha estabilizar */
        for (int c = 0; c < 4; c++) {
            if (digitalRead(COLS[c]) == LOW) {
                digitalWrite(ROWS[r], HIGH);
                *pr = r; *pc = c;
                return 1;
            }
        }
        digitalWrite(ROWS[r], HIGH);
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
        digitalWrite(ROWS[i], HIGH);
        pinMode(COLS[i], INPUT);
        pullUpDnControl(COLS[i], PUD_UP);
    }
    delay(50);

    /* ---- 1) diagnostico de repouso (nenhuma tecla pressionada) ---- */
    printf("== Diagnostico (NAO aperte nada agora) ==\n");
    int suspeita = 0;
    for (int c = 0; c < 4; c++) {
        int v = digitalRead(COLS[c]);
        printf("  coluna %d (GPIO%2d) em repouso = %d %s\n",
               c, COLS[c], v, v == 0 ? "  <-- DEVERIA SER 1!" : "");
        if (v == 0) suspeita = 1;
    }
    if (suspeita)
        printf("\n>> Alguma coluna leu 0 sem tecla: pull-up nao ativo ou fio solto.\n"
               ">> E a causa do 'printa adoidado'. Veja as dicas no README.\n\n");
    else
        printf("\n>> Repouso OK (tudo em 1). Agora pressione teclas:\n\n");

    /* ---- 2) scan sem spam (uma impressao por tecla) ---- */
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
