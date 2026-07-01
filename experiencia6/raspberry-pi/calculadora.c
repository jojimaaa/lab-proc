/*
 * calculadora.c
 * Versao de REFERENCIA em C da calculadora binaria (Experiencia 6).
 *
 * Mesma logica do calculadora.s, porem em C. Serve para:
 *   - conferir os resultados produzidos pelo Assembly;
 *   - rodar em Raspberry Pi OS de 32 bits (onde o .s AArch64 nao monta).
 *
 *   Build: gcc -O2 -o calculadora_c calculadora.c     (ou: make c)
 *   Run:   ./calculadora_c
 */
#include <stdio.h>
#include <stdint.h>
#include <string.h>

/* Converte uma string de '0'/'1' em inteiro de 64 bits sem sinal. */
static uint64_t parse_bin(const char *s) {
    uint64_t v = 0;
    for (; *s == '0' || *s == '1'; s++)
        v = (v << 1) | (uint64_t)(*s - '0');
    return v;
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

int main(void) {
    char line[64];

    printf("\n==== Calculadora Binaria ARM (C ref) - Exp 6 ====\n");
    printf("Operacoes: + - * /  e  ! (fatorial)\n");

    for (;;) {
        printf("\nOperando A (binario): ");
        if (!fgets(line, sizeof(line), stdin)) break;
        int64_t a = (int64_t)parse_bin(line);

        printf("Operacao (+ - * / !): ");
        if (!fgets(line, sizeof(line), stdin)) break;
        char op = line[0];

        int64_t res = 0;

        if (op == '!') {
            uint64_t f;
            if (factorial((uint64_t)a, &f)) {
                printf("ERRO: overflow de 64 bits no fatorial (n muito grande).\n");
                goto cont;
            }
            res = (int64_t)f;
        } else {
            printf("Operando B (binario): ");
            if (!fgets(line, sizeof(line), stdin)) break;
            int64_t b = (int64_t)parse_bin(line);

            switch (op) {
                case '+': res = a + b; break;
                case '-': res = a - b; break;
                case '*': res = a * b; break;
                case '/':
                    if (b == 0) {
                        printf("ERRO: divisao por zero (operacao invalida). Tente novamente.\n");
                        goto cont;
                    }
                    printf("Quociente: %lld   Resto: %lld\n",
                           (long long)(a / b), (long long)(a % b));
                    goto cont;
                default:
                    printf("ERRO: operacao desconhecida.\n");
                    goto cont;
            }
        }

        printf("Resultado: %lld  (binario: ", (long long)res);
        print_bin(res);
        printf(")\n");

    cont:
        printf("\nContinuar? (s/n): ");
        if (!fgets(line, sizeof(line), stdin)) break;
        if (line[0] == 'n' || line[0] == 'N') break;
    }

    printf("Encerrando. Ate a proxima.\n");
    return 0;
}
