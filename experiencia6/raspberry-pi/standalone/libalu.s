/*
 * libalu.s
 * ULA da calculadora binaria em Assembly ARM64 (AArch64), exposta como FUNCAO
 * chamavel a partir do Python (via ctypes) ou de C.
 *
 * PCS3732 - Experiencia 6 - Desafio standalone.
 * Diferente do calculadora.s (executavel com I/O por syscall), aqui NAO ha
 * entrada/saida: o Python cuida do teclado matricial e do LCD I2C, e chama
 * esta funcao so para executar a aritmetica. O "processador" continua em ASM.
 *
 * Build:  gcc -shared -fPIC -o libalu.so libalu.s     (ou: make)
 *
 * Prototipo C:
 *   int alu_calc(int op, long a, long b, long *out_result, long *out_remainder);
 *
 * Convencao (AAPCS64):
 *   w0 = op (codigo ASCII: '+' '-' '*' '/' '!')
 *   x1 = a
 *   x2 = b
 *   x3 = ponteiro p/ resultado    (quociente, no caso de '/')
 *   x4 = ponteiro p/ resto        (usado so em '/')
 *   retorno em w0:  0 = OK
 *                   1 = divisao por zero
 *                   2 = overflow de 64 bits (fatorial)
 *                   3 = operacao desconhecida
 *
 * Funcao folha: usa apenas registradores temporarios (x9..x12), nao precisa
 * salvar registradores callee-saved nem montar stack frame.
 */

        .equ CH_PLUS, 0x2B      /* '+' */
        .equ CH_MIN,  0x2D      /* '-' */
        .equ CH_MUL,  0x2A      /* '*' */
        .equ CH_DIV,  0x2F      /* '/' */
        .equ CH_FACT, 0x21      /* '!' */

        .text
        .global alu_calc
        .type   alu_calc, %function

alu_calc:
        cmp     w0, #CH_PLUS
        b.eq    .Lc_add
        cmp     w0, #CH_MIN
        b.eq    .Lc_sub
        cmp     w0, #CH_MUL
        b.eq    .Lc_mul
        cmp     w0, #CH_DIV
        b.eq    .Lc_div
        cmp     w0, #CH_FACT
        b.eq    .Lc_fact
        mov     w0, #3                  /* operacao desconhecida */
        ret

.Lc_add:
        add     x9, x1, x2
        str     x9, [x3]
        mov     w0, #0
        ret

.Lc_sub:
        sub     x9, x1, x2
        str     x9, [x3]
        mov     w0, #0
        ret

.Lc_mul:
        mul     x9, x1, x2
        str     x9, [x3]
        mov     w0, #0
        ret

.Lc_div:
        cbz     x2, .Lc_div0            /* B == 0 -> erro */
        sdiv    x9, x1, x2              /* quociente        */
        msub    x10, x9, x2, x1         /* resto = a - q*b  */
        str     x9, [x3]
        str     x10, [x4]
        mov     w0, #0
        ret
.Lc_div0:
        mov     w0, #1
        ret

.Lc_fact:
        mov     x9, x1                  /* n         */
        mov     x10, #1                 /* resultado */
        cmp     x9, #1
        b.le    .Lc_fact_done           /* 0! = 1! = 1 */
        mov     x11, #2                 /* i = 2     */
.Lc_fact_loop:
        cmp     x11, x9
        b.gt    .Lc_fact_done
        umulh   x12, x10, x11           /* parte alta do produto */
        mul     x10, x10, x11           /* parte baixa           */
        cbz     x12, .Lc_fact_next      /* alta == 0 -> ok       */
        mov     w0, #2                  /* overflow              */
        ret
.Lc_fact_next:
        add     x11, x11, #1
        b       .Lc_fact_loop
.Lc_fact_done:
        str     x10, [x3]
        mov     w0, #0
        ret

        .size alu_calc, . - alu_calc

/* Marca a pilha como nao-executavel (evita aviso do linker). */
        .section .note.GNU-stack,"",%progbits
