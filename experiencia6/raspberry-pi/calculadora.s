/*
 * calculadora.s
 * Calculadora Binaria em Assembly ARM64 (AArch64) - Raspberry Pi 3 (Cortex-A53)
 *
 * PCS3732 - Laboratorio de Processadores
 * Experiencia 6: "Arquiteturas em Duelo" - lado ARM do duelo ARM vs RISC-V.
 *
 * Le dois operandos em BINARIO de 4 bits (0 a 15) pelo teclado, executa a
 * operacao escolhida e mostra o resultado em DECIMAL e BINARIO no monitor,
 * junto do TEMPO DE EXECUCAO medido pelo contador de ciclos do ARM.
 *
 * Operacoes:  +  soma
 *             -  subtracao (resultado pode ser negativo)
 *             *  multiplicacao
 *             /  divisao inteira (quociente + resto, trata divisao por zero)
 *             !  fatorial (com deteccao de overflow de 64 bits)
 *
 * Tempo: lido com o contador virtual do ARM (cntvct_el0 / cntfrq_el0).
 *   Uma operacao isolada e mais rapida que a resolucao do contador, entao a
 *   operacao e repetida REPS vezes; reportamos o tempo total e o tempo/op.
 *   (No RISC-V o analogo seria o CSR `time`/`cycle`.)
 *
 * Roda SOBRE o Linux (Raspberry Pi OS 64-bit) usando syscalls. NAO usa libc.
 *
 *   Build:  make            (ou: as -o calculadora.o calculadora.s && ld -o calculadora calculadora.o)
 *   Run:    ./calculadora
 *
 * Requer SO de 64 bits: confira com `uname -m`  ->  deve responder "aarch64".
 *
 * Mapa de registradores no laco principal (callee-saved, nao tocados pelas rotinas):
 *   x19 = operando A   (depois da medicao: tempo total em ns)
 *   x20 = operando B   (depois da medicao: tempo por operacao em ns)
 *   w22 = caractere da operacao
 *   x21 = resultado (soma/sub/mul/fatorial)
 *   x23 = quociente     x24 = resto (divisao)
 *   x25 = flag de overflow (fatorial)
 *   x26 = contador de repeticoes
 *   x27 = t0 (cntvct)   x28 = t1 (cntvct)
 */

/* ---- Numeros de syscall (AArch64 / Linux) ---- */
        .equ SYS_READ,  63
        .equ SYS_WRITE, 64
        .equ SYS_EXIT,  93

        .equ STDIN,  0
        .equ STDOUT, 1

        .equ BUFSZ, 64

/* ---- Repeticoes para medir tempo (op unica < resolucao do contador) ---- */
        .equ REPS,    1000000   /* 0x000F4240 */
        .equ REPS_LO, 0x4240
        .equ REPS_HI, 0x000F

/* ---- 1 000 000 000 (ns por segundo) = 0x3B9ACA00 ---- */
        .equ NS_LO,   0xCA00
        .equ NS_HI,   0x3B9A

/* ---- Caracteres (em hex, para nao depender da sintaxe de char do montador) ---- */
        .equ CH_0,    0x30      /* '0' */
        .equ CH_1,    0x31      /* '1' */
        .equ CH_PLUS, 0x2B      /* '+' */
        .equ CH_MIN,  0x2D      /* '-' */
        .equ CH_MUL,  0x2A      /* '*' */
        .equ CH_DIV,  0x2F      /* '/' */
        .equ CH_FACT, 0x21      /* '!' */
        .equ CH_n,    0x6E      /* 'n' */
        .equ CH_N,    0x4E      /* 'N' */
        .equ CH_MINUS,0x2D      /* '-' (sinal) */

/* ===================================================================== */
.section .data

banner:     .ascii  "\n==== Calculadora Binaria ARM (AArch64) - Exp 6 ====\n"
            .ascii  "Operacoes: + - * /  e  ! (fatorial)\n"
banner_len = . - banner

msg_a:      .ascii  "\nOperando A (binario, 4 bits 0..15): "
msg_a_len = . - msg_a

msg_op:     .ascii  "Operacao (+ - * / !): "
msg_op_len = . - msg_op

msg_b:      .ascii  "Operando B (binario, 4 bits 0..15): "
msg_b_len = . - msg_b

msg_res:    .ascii  "Resultado: "
msg_res_len = . - msg_res

msg_bin:    .ascii  "  (binario: "
msg_bin_len = . - msg_bin

msg_close:  .ascii  ")\n"
msg_close_len = . - msg_close

msg_quo:    .ascii  "Quociente: "
msg_quo_len = . - msg_quo

msg_rem:    .ascii  "   Resto: "
msg_rem_len = . - msg_rem

msg_nl:     .ascii  "\n"
msg_nl_len = . - msg_nl

msg_time1:  .ascii  "Tempo: "
msg_time1_len = . - msg_time1

msg_time2:  .ascii  " ns  ("
msg_time2_len = . - msg_time2

msg_time3:  .ascii  " repeticoes)  =>  "
msg_time3_len = . - msg_time3

msg_time4:  .ascii  " ns/operacao  [cntvct_el0]\n"
msg_time4_len = . - msg_time4

msg_divzero:.ascii  "ERRO: divisao por zero (operacao invalida). Tente novamente.\n"
msg_divzero_len = . - msg_divzero

msg_ovf:    .ascii  "ERRO: overflow de 64 bits no fatorial (n muito grande).\n"
msg_ovf_len = . - msg_ovf

msg_badop:  .ascii  "ERRO: operacao desconhecida.\n"
msg_badop_len = . - msg_badop

msg_range:  .ascii  "ERRO: entrada deve ter 4 bits (0 a 15, ex.: 0000 a 1111). Tente novamente.\n"
msg_range_len = . - msg_range

msg_cont:   .ascii  "\nContinuar? (s/n): "
msg_cont_len = . - msg_cont

msg_bye:    .ascii  "Encerrando. Ate a proxima.\n"
msg_bye_len = . - msg_bye

/* ===================================================================== */
.section .bss
        .align 3
bufA:    .skip BUFSZ
bufOp:   .skip BUFSZ
bufB:    .skip BUFSZ
bufCont: .skip BUFSZ

        .align 3
numbuf:  .skip 32        /* buffer p/ conversao decimal (reverso)  */
numbuf_end:

        .align 3
binbuf:  .skip 80        /* buffer p/ conversao binaria (reverso)  */
binbuf_end:

/* ===================================================================== */
.section .text
        .global _start

_start:
        /* banner inicial */
        adr     x0, banner
        mov     x1, #banner_len
        bl      write_str

.Lmain_loop:
        /* ---- INPUT: operando A (4 bits, valores de 0 a 15) ---- */
        adr     x0, msg_a
        mov     x1, #msg_a_len
        bl      write_str
        adr     x0, bufA
        mov     x1, #BUFSZ
        bl      read_line
        adr     x0, bufA
        bl      parse_bin
        cmp     x0, #15                 /* limite de 4 bits (0..15)     */
        b.hi    .La_range               /* > 15 (sem sinal) -> invalido */
        mov     x19, x0                 /* A */

        /* ---- INPUT: operacao (decodificador de OpCode) ---- */
        adr     x0, msg_op
        mov     x1, #msg_op_len
        bl      write_str
        adr     x0, bufOp
        mov     x1, #BUFSZ
        bl      read_line
        adr     x0, bufOp
        ldrb    w22, [x0]               /* caractere da operacao */

        /* fatorial usa apenas A -> vai direto p/ medicao (nao pede B) */
        cmp     w22, #CH_FACT
        b.eq    .Ltimed

.Lread_b:
        /* ---- INPUT: operando B (4 bits, valores de 0 a 15) ---- */
        adr     x0, msg_b
        mov     x1, #msg_b_len
        bl      write_str
        adr     x0, bufB
        mov     x1, #BUFSZ
        bl      read_line
        adr     x0, bufB
        bl      parse_bin
        cmp     x0, #15                 /* limite de 4 bits (0..15)     */
        b.hi    .Lb_range               /* > 15 (sem sinal) -> invalido */
        mov     x20, x0                 /* B */

        /* ---- decodificacao do OpCode + validacao (feita FORA da medicao) ---- */
        cmp     w22, #CH_PLUS
        b.eq    .Ltimed
        cmp     w22, #CH_MIN
        b.eq    .Ltimed
        cmp     w22, #CH_MUL
        b.eq    .Ltimed
        cmp     w22, #CH_DIV
        b.eq    .Lchk_div

        /* operacao invalida */
        adr     x0, msg_badop
        mov     x1, #msg_badop_len
        bl      write_str
        b       .Lask_cont

.Lchk_div:
        cbz     x20, .Ldiv_zero         /* B == 0 -> erro, sem medir */
        b       .Ltimed

/* ============ MEDICAO DE TEMPO (contador virtual do ARM) ============ */
.Ltimed:
        mov     x26, #REPS_LO
        movk    x26, #REPS_HI, lsl #16  /* x26 = REPS (contador)          */
        mrs     x27, cntvct_el0         /* t0 = contador virtual (ticks)  */

.Ltimed_loop:
        /* decodificador de OpCode -> ULA */
        cmp     w22, #CH_PLUS
        b.eq    .Lt_add
        cmp     w22, #CH_MIN
        b.eq    .Lt_sub
        cmp     w22, #CH_MUL
        b.eq    .Lt_mul
        cmp     w22, #CH_DIV
        b.eq    .Lt_div
        /* [!] FAT : fatorial iterativo com monitor de overflow */
        mov     x0, x19
        bl      factorial               /* x0 = A!, x1 = overflow */
        mov     x21, x0
        mov     x25, x1
        b       .Lt_next
.Lt_add:                                /* [+] ADD */
        add     x21, x19, x20
        b       .Lt_next
.Lt_sub:                                /* [-] SUB (pode dar negativo) */
        sub     x21, x19, x20
        b       .Lt_next
.Lt_mul:                                /* [*] MUL */
        mul     x21, x19, x20
        b       .Lt_next
.Lt_div:                                /* [/] DIV : quociente + resto */
        sdiv    x23, x19, x20
        msub    x24, x23, x20, x19      /* resto = A - quoc*B */
        mov     x21, x23
.Lt_next:
        subs    x26, x26, #1
        b.ne    .Ltimed_loop

        mrs     x28, cntvct_el0         /* t1 */

        /* fatorial com overflow -> erro (nao ocorre com 4 bits; protecao N-bits) */
        cmp     w22, #CH_FACT
        b.ne    .Lcalc_time
        cbnz    x25, .Lfact_ovf

.Lcalc_time:
        /* ns_total = (t1 - t0) * 1e9 / cntfrq ;  ns_op = ns_total / REPS */
        sub     x9,  x28, x27           /* delta de ticks              */
        mrs     x10, cntfrq_el0         /* frequencia do contador (Hz) */
        mov     x11, #NS_LO
        movk    x11, #NS_HI, lsl #16    /* x11 = 1 000 000 000         */
        mul     x12, x9, x11
        udiv    x19, x12, x10           /* x19 = tempo total (ns)      */
        mov     x9,  #REPS_LO
        movk    x9,  #REPS_HI, lsl #16
        udiv    x20, x19, x9            /* x20 = tempo por operacao(ns)*/

        /* ---- imprime o RESULTADO (Binario -> ASCII -> buffer de video) ---- */
        cmp     w22, #CH_DIV
        b.eq    .Lprint_div
        adr     x0, msg_res
        mov     x1, #msg_res_len
        bl      write_str
        mov     x0, x21
        bl      print_dec
        adr     x0, msg_bin
        mov     x1, #msg_bin_len
        bl      write_str
        mov     x0, x21
        bl      print_bin
        adr     x0, msg_close
        mov     x1, #msg_close_len
        bl      write_str
        b       .Lprint_time
.Lprint_div:
        adr     x0, msg_quo
        mov     x1, #msg_quo_len
        bl      write_str
        mov     x0, x23
        bl      print_dec
        adr     x0, msg_rem
        mov     x1, #msg_rem_len
        bl      write_str
        mov     x0, x24
        bl      print_dec
        adr     x0, msg_nl
        mov     x1, #msg_nl_len
        bl      write_str

        /* ---- imprime o TEMPO de execucao ---- */
.Lprint_time:
        adr     x0, msg_time1
        mov     x1, #msg_time1_len
        bl      write_str
        mov     x0, x19                 /* tempo total (ns) */
        bl      print_dec
        adr     x0, msg_time2
        mov     x1, #msg_time2_len
        bl      write_str
        mov     x0, #REPS_LO
        movk    x0, #REPS_HI, lsl #16   /* REPS */
        bl      print_dec
        adr     x0, msg_time3
        mov     x1, #msg_time3_len
        bl      write_str
        mov     x0, x20                 /* tempo por operacao (ns) */
        bl      print_dec
        adr     x0, msg_time4
        mov     x1, #msg_time4_len
        bl      write_str
        b       .Lask_cont

/* ---- erros que abortam a operacao (sem medir tempo) ---- */
.Ldiv_zero:
        adr     x0, msg_divzero
        mov     x1, #msg_divzero_len
        bl      write_str
        b       .Lask_cont
.Lfact_ovf:
        adr     x0, msg_ovf
        mov     x1, #msg_ovf_len
        bl      write_str
        b       .Lask_cont

/* ---- entrada fora da faixa de 4 bits (0..15): avisa e re-pergunta ---- */
.La_range:
        adr     x0, msg_range
        mov     x1, #msg_range_len
        bl      write_str
        b       .Lmain_loop             /* re-pergunta A */
.Lb_range:
        adr     x0, msg_range
        mov     x1, #msg_range_len
        bl      write_str
        b       .Lread_b                /* re-pergunta apenas B */

/* ---- perguntar se continua ---- */
.Lask_cont:
        adr     x0, msg_cont
        mov     x1, #msg_cont_len
        bl      write_str
        adr     x0, bufCont
        mov     x1, #BUFSZ
        bl      read_line
        adr     x0, bufCont
        ldrb    w9, [x0]
        cmp     w9, #CH_n
        b.eq    .Lexit
        cmp     w9, #CH_N
        b.eq    .Lexit
        b       .Lmain_loop

.Lexit:
        adr     x0, msg_bye
        mov     x1, #msg_bye_len
        bl      write_str
        mov     x0, #0
        mov     x8, #SYS_EXIT
        svc     #0

/* ===================================================================== */
/* write_str(x0 = ptr, x1 = len) -> escreve no STDOUT                    */
/* clobbers: x0,x1,x2,x8                                                  */
write_str:
        mov     x2, x1                  /* count */
        mov     x1, x0                  /* buf   */
        mov     x0, #STDOUT
        mov     x8, #SYS_WRITE
        svc     #0
        ret

/* read_line(x0 = buf, x1 = maxlen) -> x0 = bytes lidos                  */
/* clobbers: x0,x1,x2,x8                                                  */
read_line:
        mov     x2, x1                  /* count */
        mov     x1, x0                  /* buf   */
        mov     x0, #STDIN
        mov     x8, #SYS_READ
        svc     #0
        ret

/* parse_bin(x0 = ponteiro p/ string) -> x0 = valor inteiro             */
/* Le digitos '0'/'1' ate encontrar qualquer outro caractere.           */
/* clobbers: x9,x10,x11                                                   */
parse_bin:
        mov     x9, x0                  /* ponteiro */
        mov     x10, #0                 /* acumulador */
.Lpb_next:
        ldrb    w11, [x9]
        cmp     w11, #CH_0
        b.lt    .Lpb_done               /* < '0'  -> fim */
        cmp     w11, #CH_1
        b.gt    .Lpb_done               /* > '1'  -> fim */
        lsl     x10, x10, #1            /* acc <<= 1     */
        sub     w11, w11, #CH_0         /* 0 ou 1        */
        add     x10, x10, x11           /* acc += bit    */
        add     x9, x9, #1
        b       .Lpb_next
.Lpb_done:
        mov     x0, x10
        ret

/* factorial(x0 = n) -> x0 = n!, x1 = 1 se houve overflow de 64 bits     */
/* Para no PRIMEIRO overflow (umulh != 0); no maximo ~21 iteracoes.       */
/* clobbers: x9..x13                                                      */
factorial:
        mov     x9, x0                  /* n          */
        mov     x10, #1                 /* resultado  */
        mov     x11, #0                 /* flag ovf   */
        cmp     x9, #1
        b.le    .Lfact_end              /* 0! = 1! = 1 */
        mov     x12, #2                 /* i = 2      */
.Lfact_loop:
        cmp     x12, x9
        b.gt    .Lfact_end
        umulh   x13, x10, x12           /* parte alta do produto */
        mul     x10, x10, x12           /* parte baixa           */
        cbz     x13, .Lfact_step        /* alta == 0 -> ok       */
        mov     x11, #1                 /* overflow!             */
        b       .Lfact_end
.Lfact_step:
        add     x12, x12, #1
        b       .Lfact_loop
.Lfact_end:
        mov     x0, x10
        mov     x1, x11
        ret

/* print_dec(x0 = valor com sinal) -> imprime em decimal                 */
/* clobbers: x9..x14                                                      */
print_dec:
        mov     x9, x0
        adr     x10, numbuf_end         /* escreve de tras p/ frente */
        mov     x11, #0                 /* flag negativo */
        cmp     x9, #0
        b.ge    .Lpd_conv
        mov     x11, #1
        neg     x9, x9
.Lpd_conv:
        mov     x12, #10
.Lpd_loop:
        udiv    x13, x9, x12            /* q = n/10            */
        msub    x14, x13, x12, x9       /* r = n - q*10        */
        add     x14, x14, #CH_0         /* digito ASCII        */
        sub     x10, x10, #1
        strb    w14, [x10]
        mov     x9, x13
        cbnz    x9, .Lpd_loop
        cbz     x11, .Lpd_out
        sub     x10, x10, #1
        mov     w14, #CH_MINUS
        strb    w14, [x10]
.Lpd_out:
        adr     x12, numbuf_end
        sub     x1, x12, x10            /* comprimento */
        mov     x0, x10                 /* ponteiro    */
        b       write_str               /* tail-call: o ret de write_str volta ao chamador */

/* print_bin(x0 = valor com sinal) -> imprime magnitude em binario       */
/* Mostra sinal-modulo (prefixo '-' para negativos) para leitura clara.  */
/* clobbers: x9..x14                                                      */
print_bin:
        mov     x9, x0
        adr     x10, binbuf_end
        mov     x11, #0
        cmp     x9, #0
        b.ge    .Lpbn_conv
        mov     x11, #1
        neg     x9, x9
.Lpbn_conv:
.Lpbn_loop:
        and     x14, x9, #1
        add     x14, x14, #CH_0
        sub     x10, x10, #1
        strb    w14, [x10]
        lsr     x9, x9, #1
        cbnz    x9, .Lpbn_loop
        cbz     x11, .Lpbn_out
        sub     x10, x10, #1
        mov     w14, #CH_MINUS
        strb    w14, [x10]
.Lpbn_out:
        adr     x12, binbuf_end
        sub     x1, x12, x10
        mov     x0, x10
        b       write_str
