/*
 * calculadora.c - Calculadora binaria STANDALONE em C (Experiencia 6 - Desafio).
 *
 * Placa: Freenove Projects Board for Raspberry Pi.
 * Entrada: teclado matricial 4x4 (GPIO).   Saida: LCD 16x2 (I2C, PCF8574).
 * Biblioteca de hardware: wiringPi (padrao dos tutoriais Freenove em C).
 *
 * A aritmetica (ULA) NAO esta aqui: e a funcao alu_calc(), escrita em
 * Assembly ARM64 (libalu.s) e linkada a este C. O C cuida so das bordas.
 *
 *   Build:  make            (gcc calculadora.c libalu.s -lwiringPi)
 *   Run:    sudo ./calculadora
 *
 * Ajuste os pinos (ROWS/COLS) e o endereco do LCD (LCD_ADDR) conforme a sua
 * ligacao na Freenove board. I2C fica sempre em GPIO2 (SDA) / GPIO3 (SCL).
 */
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <wiringPi.h>
#include <wiringPiI2C.h>

/* ---- ULA em Assembly (libalu.s) ----
 * retorno: 0=OK  1=div/0  2=overflow  3=operacao invalida */
extern int alu_calc(int op, long a, long b, long *out_result, long *out_remainder);

/* ==================== teclado matricial 4x4 ==================== */
static const int ROWS[4] = {16, 20, 21, 26};   /* BCM, saidas   */
static const int COLS[4] = {19, 13, 6, 5};     /* BCM, entradas */
static const char KEYS[4][4] = {
    {'1', '2', '3', 'A'},
    {'4', '5', '6', 'B'},
    {'7', '8', '9', 'C'},
    {'*', '0', '#', 'D'},
};

/* Varredura em PULL-DOWN (ativo-alto): linhas em repouso LOW, acionadas em
 * HIGH; colunas com pull-down (repouso 0) -> tecla leva a coluna a 1. */
static void keypad_setup(void) {
    for (int i = 0; i < 4; i++) {
        pinMode(ROWS[i], OUTPUT);
        digitalWrite(ROWS[i], LOW);
        pinMode(COLS[i], INPUT);
        pullUpDnControl(COLS[i], PUD_DOWN);
    }
}

static char keypad_scan(void) {
    for (int r = 0; r < 4; r++) {
        digitalWrite(ROWS[r], HIGH);
        delayMicroseconds(50);
        for (int c = 0; c < 4; c++) {
            if (digitalRead(COLS[c]) == HIGH) {
                digitalWrite(ROWS[r], LOW);
                return KEYS[r][c];
            }
        }
        digitalWrite(ROWS[r], LOW);
    }
    return 0;
}

/* Bloqueia ate uma tecla ser pressionada; espera soltar (debounce). */
static char keypad_getkey(void) {
    for (;;) {
        char k = keypad_scan();
        if (k) {
            delay(30);
            while (keypad_scan()) delay(10);
            return k;
        }
        delay(5);
    }
}

/* ==================== LCD 16x2 via PCF8574 (I2C) ==================== */
#define LCD_ADDR 0x27       /* troque p/ 0x3F conforme 'i2cdetect -y 1' */
#define LCD_RS   0x01
#define LCD_EN   0x04
#define LCD_BL   0x08       /* backlight */

static int lcd_fd;

static void lcd_raw(int data) {
    wiringPiI2CWrite(lcd_fd, data | LCD_BL);
    delayMicroseconds(100);
}
static void lcd_strobe(int data) {
    lcd_raw(data | LCD_EN);
    delayMicroseconds(500);
    lcd_raw(data & ~LCD_EN);
    delayMicroseconds(100);
}
static void lcd_send(int value, int mode) {   /* mode: 0=comando, LCD_RS=dado */
    lcd_strobe(mode | (value & 0xF0));
    lcd_strobe(mode | ((value << 4) & 0xF0));
}
static void lcd_init(int addr) {
    lcd_fd = wiringPiI2CSetup(addr);
    const int seq[] = {0x33, 0x32, 0x28, 0x0C, 0x06, 0x01};  /* modo 4 bits */
    for (int i = 0; i < 6; i++) lcd_send(seq[i], 0);
    delay(5);
}
static void lcd_line(int row, const char *text) {   /* escreve 16 col (preenche) */
    static const int off[2] = {0x00, 0x40};
    lcd_send(0x80 | off[row], 0);
    int i = 0;
    for (; text[i] && i < 16; i++) lcd_send((unsigned char)text[i], LCD_RS);
    for (; i < 16; i++)            lcd_send(' ', LCD_RS);
}

/* ==================== calculadora ==================== */
static char op_of(char k) {
    switch (k) {
        case 'A': return '+';
        case 'B': return '-';
        case 'C': return '*';
        case 'D': return '/';
        case '*': return '!';
        default:  return 0;
    }
}

static long bin_to_long(const char *s) {
    long v = 0;
    for (; *s == '0' || *s == '1'; s++) v = (v << 1) | (*s - '0');
    return v;
}

/* inteiro com sinal -> string binaria (sinal-modulo) */
static void to_bin_str(long v, char *buf) {
    char tmp[80];
    int i = 0, j = 0;
    unsigned long m = v < 0 ? (unsigned long)(-v) : (unsigned long)v;
    if (m == 0) tmp[i++] = '0';
    while (m) { tmp[i++] = '0' + (char)(m & 1); m >>= 1; }
    if (v < 0) buf[j++] = '-';
    while (i) buf[j++] = tmp[--i];
    buf[j] = '\0';
}

int main(void) {
    if (wiringPiSetupGpio() < 0) {            /* numeracao BCM */
        fprintf(stderr, "Falha ao iniciar wiringPi (tente com sudo).\n");
        return 1;
    }
    keypad_setup();
    lcd_init(LCD_ADDR);

    lcd_line(0, "Calc Bin ARM");
    lcd_line(1, "Exp6 - Desafio C");

    for (;;) {
        char a_bits[8] = "", b_bits[8] = "", line[32];
        int alen = 0, blen = 0;
        char op = 0;                          /* '+','-','*','/','!' ou 0 */

        lcd_line(0, "?");
        lcd_line(1, "0/1  op A-D");

        /* ---- monta A, operacao e B pelo teclado ---- */
        for (;;) {
            char k = keypad_getkey();
            if (k == '2') { op = 0; break; }  /* limpar -> reinicia rodada */

            if (op == 0) {                    /* montando A / escolhendo operacao */
                if ((k == '0' || k == '1') && alen < 4) {
                    a_bits[alen++] = k; a_bits[alen] = 0;
                } else if (op_of(k) && alen > 0) {
                    op = op_of(k);
                    lcd_line(1, op == '!' ? "# calcular" : "0/1 B  #=calc");
                } else continue;
            } else if (op != '!') {           /* montando B */
                if ((k == '0' || k == '1') && blen < 4) {
                    b_bits[blen++] = k; b_bits[blen] = 0;
                } else if (k == '#' && blen > 0) break;
                else continue;
            } else {                          /* fatorial: so espera '#' */
                if (k == '#') break;
                else continue;
            }

            if (op == 0)
                snprintf(line, sizeof line, "%s", alen ? a_bits : "?");
            else if (op == '!')
                snprintf(line, sizeof line, "%s !", a_bits);
            else
                snprintf(line, sizeof line, "%s %c %s", a_bits, op, blen ? b_bits : "?");
            lcd_line(0, line);
        }
        if (op == 0) continue;                /* usuario limpou */

        /* ---- calcula via ULA em Assembly ---- */
        long a = bin_to_long(a_bits);
        long b = blen ? bin_to_long(b_bits) : 0;
        long res = 0, rem = 0;
        int st = alu_calc((int)op, a, b, &res, &rem);

        if (st == 1)       lcd_line(1, "ERRO: div por 0");
        else if (st == 2)  lcd_line(1, "ERRO: overflow");
        else if (st == 3)  lcd_line(1, "ERRO: operacao");
        else if (op == '/') {
            snprintf(line, sizeof line, "q=%ld r=%ld", res, rem);
            lcd_line(1, line);
        } else {
            char bs[80];
            to_bin_str(res, bs);
            snprintf(line, sizeof line, "=%ld b%s", res, bs);
            if (strlen(line) > 16) snprintf(line, sizeof line, "=%ld", res);
            lcd_line(1, line);
        }

        keypad_getkey();                      /* qualquer tecla volta ao inicio */
    }
    return 0;
}
