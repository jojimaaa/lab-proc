/*
 * calculadora.s
 * Calculadora Binaria em Assembly ARM64 (AArch64) - Raspberry Pi 3 (Cortex-A53)
 *
 * PCS3732 - Laboratorio de Processadores
 * Experiencia 6: "Arquiteturas em Duelo" - lado ARM do duelo ARM vs RISC-V.
 *
 * Le dois operandos em BINARIO pelo teclado, executa a operacao escolhida
 * e mostra o resultado em DECIMAL e em BINARIO no monitor (HDMI/VGA).
 *
 * Operacoes:  +  soma
 *             -  subtracao (resultado pode ser negativo)
 *             *  multiplicacao
 *             /  divisao inteira (quociente + resto, trata divisao por zero)
 *             !  fatorial (com deteccao de overflow de 64 bits)
 *
 * Roda SOBRE o Linux (Raspberry Pi OS 64-bit) usando syscalls. NAO usa libc.
 *
 *   Build:  make            (ou: as -o calculadora.o calculadora.s && ld -o calculadora calculadora.o)
 *   Run:    ./calculadora
 *
 * Requer SO de 64 bits: confira com `uname -m`  ->  deve responder "aarch64".
 *
 * Mapa de registradores no laco principal (callee-saved, nao tocados pelas rotinas):
 *   x19 = operando A / acumulador do resultado
 *   x20 = operando B
 *   w22 = caractere da operacao
 *   x23 = quociente (divisao)   x24 = resto (divisao)
 */

/* ---- Numeros de syscall (AArch64 / Linux) ---- */
        .equ SYS_READ,  63
        .equ SYS_WRITE, 64
        .equ SYS_EXIT,  93

        .equ STDIN,  0
        .equ STDOUT, 1

        .equ BUFSZ, 64

/* ---- Caracteres (em hex, para nao depender da sintaxe de char do montador) ---- */
        .equ CH_0,    0x30      /* '0' */
        .equ CH_1,    0x31      /* '1' */
        .equ CH_9,    0x39      /* '9' (nao usado, referencia) */
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

msg_a:      .ascii  "\nOperando A (binario): "
msg_a_len = . - msg_a

msg_op:     .ascii  "Operacao (+ - * / !): "
msg_op_len = . - msg_op

msg_b:      .ascii  "Operando B (binario): "
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

msg_divzero:.ascii  "ERRO: divisao por zero (operacao invalida). Tente novamente.\n"
msg_divzero_len = . - msg_divzero

msg_ovf:    .ascii  "ERRO: overflow de 64 bits no fatorial (n muito grande).\n"
msg_ovf_len = . - msg_ovf

msg_badop:  .ascii  "ERRO: operacao desconhecida.\n"
msg_badop_len = . - msg_badop

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
        /* ---- INPUT: operando A ---- */
        adr     x0, msg_a
        mov     x1, #msg_a_len
        bl      write_str
        adr     x0, bufA
        mov     x1, #BUFSZ
        bl      read_line
        adr     x0, bufA
        bl      parse_bin
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

        /* fatorial usa apenas A -> desvia antes de pedir B */
        cmp     w22, #CH_FACT
        b.eq    .Ldo_fact

        /* ---- INPUT: operando B ---- */
        adr     x0, msg_b
        mov     x1, #msg_b_len
        bl      write_str
        adr     x0, bufB
        mov     x1, #BUFSZ
        bl      read_line
        adr     x0, bufB
        bl      parse_bin
        mov     x20, x0                 /* B */

        /* ---- decodificacao do OpCode ---- */
        cmp     w22, #CH_PLUS
        b.eq    .Ldo_add
        cmp     w22, #CH_MIN
        b.eq    .Ldo_sub
        cmp     w22, #CH_MUL
        b.eq    .Ldo_mul
        cmp     w22, #CH_DIV
        b.eq    .Ldo_div

        /* operacao invalida */
        adr     x0, msg_badop
        mov     x1, #msg_badop_len
        bl      write_str
        b       .Lask_cont

/* ---- [+] ADD : instrucao direta do pipeline ---- */
.Ldo_add:
        add     x19, x19, x20
        b       .Lshow

/* ---- [-] SUB : subtracao (pode dar negativo) ---- */
.Ldo_sub:
        sub     x19, x19, x20
        b       .Lshow

/* ---- [*] MUL ---- */
.Ldo_mul:
        mul     x19, x19, x20
        b       .Lshow

/* ---- [/] DIV : trata B == 0 sem derrubar o programa ---- */
.Ldo_div:
        cbz     x20, .Ldiv_zero
        sdiv    x23, x19, x20           /* quociente               */
        msub    x24, x23, x20, x19      /* resto = A - quoc*B       */

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
        b       .Lask_cont
.Ldiv_zero:
        adr     x0, msg_divzero
        mov     x1, #msg_divzero_len
        bl      write_str
        b       .Lask_cont

/* ---- [!] FAT : fatorial iterativo com monitor de overflow ---- */
.Ldo_fact:
        mov     x0, x19
        bl      factorial               /* x0 = A!, x1 = flag overflow */
        cbnz    x1, .Lfact_ovf
        mov     x19, x0
        b       .Lshow
.Lfact_ovf:
        adr     x0, msg_ovf
        mov     x1, #msg_ovf_len
        bl      write_str
        b       .Lask_cont

/* ---- saida: decimal + binario (Binario -> ASCII -> buffer de video) ---- */
.Lshow:
        adr     x0, msg_res
        mov     x1, #msg_res_len
        bl      write_str
        mov     x0, x19
        bl      print_dec
        adr     x0, msg_bin
        mov     x1, #msg_bin_len
        bl      write_str
        mov     x0, x19
        bl      print_bin
        adr     x0, msg_close
        mov     x1, #msg_close_len
        bl      write_str

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
