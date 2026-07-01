/*
 * calculadora.c
 * Versao de REFERENCIA em C da calculadora binaria (Experiencia 6).
 *
 * Mesma logica do calculadora.s, porem em C. Serve para:
 *   - conferir os resultados produzidos pelo Assembly;
 *   - rodar em Raspberry Pi OS de 32 bits (onde o .s AArch64 nao monta).
 *
 * Tambem mede o TEMPO DE EXECUCAO. Aqui usamos clock_gettime(CLOCK_MONOTONIC)
 * (portavel). Como uma operacao isolada e mais rapida que a resolucao do
 * relogio, repetimos REPS vezes e reportamos total + ns/operacao. Os acessos
 * `volatile` (leitura dos operandos e escrita no sink) impedem o -O2 de
 * remover ou "iar" o laco -- portavel em ARM 32 e 64 bits.
 *
 *   Build: gcc -O2 -o calculadora_c calculadora.c     (ou: make c)
 *   Run:   ./calculadora_c
 */
#define _POSIX_C_SOURCE 199309L
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <time.h>

#define REPS 1000000    /* repeticoes p/ medir (op unica < resolucao do relogio) */

/* Converte uma string de '0'/'1' em inteiro de 64 bits sem sinal. */
static uint64_t parse_bin(const char *s) {
    uint64_t v = 0;
    for (; *s == '0' || *s == '1'; s++)
        v = (v << 1) | (uint64_t)(*s - '0');
    return v;
}

/* Le um operando de 4 bits (0..15), re-perguntando enquanto for invalido. */
static uint64_t read_operand(const char *prompt) {
    char line[64];
    for (;;) {
        printf("%s", prompt);
        if (!fgets(line, sizeof(line), stdin)) return 0;
        uint64_t v = parse_bin(line);
        if (v <= 15) return v;
        printf("ERRO: entrada deve ter 4 bits (0 a 15, ex.: 0000 a 1111). Tente novamente.\n");
    }
}

/* Imprime um inteiro com sinal em binario (sinal-modulo, para leitura clara). */
static void print_bin(int64_t x) {
    char buf[80];
    int i = (int)sizeof(buf);
    int neg = x < 0;
    uint64_t m = neg ? (uint64_t)(-x) : (uint64_t)x;
    buf[--i] = '\0';
    do { buf[--i] = (char)('0' + (m & 1)); m >>= 1; } while (m);
    if (neg) buf[--i] = '-';
    fputs(&buf[i], stdout);
}

/* Fatorial com deteccao de overflow de 64 bits. Retorna 1 se estourou. */
static int factorial(uint64_t n, uint64_t *out) {
    uint64_t r = 1;
    for (uint64_t i = 2; i <= n; i++) {
        if (r > UINT64_MAX / i) return 1;   /* overflow */
        r *= i;
    }
    *out = r;
    return 0;
}

/* Relogio monotonico em nanossegundos. */
static uint64_t now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

int main(void) {
    char line[64];

    printf("\n==== Calculadora Binaria ARM (C ref) - Exp 6 ====\n");
    printf("Operacoes: + - * /  e  ! (fatorial)\n");

    for (;;) {
        int64_t a = (int64_t)read_operand("\nOperando A (binario, 4 bits 0..15): ");

        printf("Operacao (+ - * / !): ");
        if (!fgets(line, sizeof(line), stdin)) break;
        char op = line[0];

        /* ---- validacao (fora da medicao) ---- */
        if (op != '+' && op != '-' && op != '*' && op != '/' && op != '!') {
            printf("ERRO: operacao desconhecida.\n");
            goto cont;
        }

        int64_t b = 0;
        if (op != '!')
            b = (int64_t)read_operand("Operando B (binario, 4 bits 0..15): ");

        if (op == '/' && b == 0) {
            printf("ERRO: divisao por zero (operacao invalida). Tente novamente.\n");
            goto cont;
        }
        uint64_t fchk;
        if (op == '!' && factorial((uint64_t)a, &fchk)) {
            printf("ERRO: overflow de 64 bits no fatorial (n muito grande).\n");
            goto cont;
        }

        /* ---- medicao de tempo ---- */
        /* operandos e sink volatile: o compilador nao pode "iar" o calculo    */
        /* para fora do laco nem descarta-lo (portavel, sem inline asm).        */
        volatile int64_t va = a, vb = b;
        volatile int64_t sink = 0;
        int64_t res = 0, q = 0, r = 0;
        uint64_t t0 = now_ns();
        for (int k = 0; k < REPS; k++) {
            int64_t aa = va, bb = vb;           /* leituras volatile */
            switch (op) {
                case '+': res = aa + bb; break;
                case '-': res = aa - bb; break;
                case '*': res = aa * bb; break;
                case '/': q = aa / bb; r = aa % bb; res = q; break;
                case '!': { uint64_t f; factorial((uint64_t)aa, &f); res = (int64_t)f; break; }
            }
            sink = res;                         /* escrita volatile (consome) */
        }
        (void)sink;
        uint64_t t1 = now_ns();
        uint64_t total_ns = t1 - t0;
        uint64_t per_op   = total_ns / REPS;

        /* ---- resultado ---- */
        if (op == '/') {
            printf("Quociente: %lld   Resto: %lld\n", (long long)q, (long long)r);
        } else {
            printf("Resultado: %lld  (binario: ", (long long)res);
            print_bin(res);
            printf(")\n");
        }

        /* ---- tempo ---- */
        printf("Tempo: %llu ns  (%d repeticoes)  =>  %llu ns/operacao  [clock_gettime]\n",
               (unsigned long long)total_ns, REPS, (unsigned long long)per_op);

    cont:
        printf("\nContinuar? (s/n): ");
        if (!fgets(line, sizeof(line), stdin)) break;
        if (line[0] == 'n' || line[0] == 'N') break;
    }

    printf("Encerrando. Ate a proxima.\n");
    return 0;
}
