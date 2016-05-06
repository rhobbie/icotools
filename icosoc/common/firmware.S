.section .init
.global main

/* begin: custom PicoRV32 opcodes */

#define q0 0
#define q1 1
#define q2 2
#define q3 3

.macro getq rd qs
custom0 \rd,\qs,0,0
.endm

.macro setq qd rs
custom0 \qd,\rs,0,1
.endm

.macro retirq
custom0 0,0,0,2
.endm

.macro maskirq rd rs
custom0 \rd,\rs,0,3
.endm

.macro waitirq rd
custom0 \rd,0,0,4
.endm

.macro timer rd rs
custom0 \rd,\rs,0,5
.endm

/* end: custom PicoRV32 opcodes */


reset_vec:
	// no more than 8 bytes here !
	j start

.balign 8
irq_handler_addr:
	.dword 0x0000000000000000

.balign 16
irq_vec:
	/* save registers */

	setq q2, x1
	setq q3, x2

	// x2 is the stack pointer
	lui x2, %hi(4096 - 4*32)
	addi x2, x2, %lo(4096 - 4*32)

	getq x1, q0
	sw x1,   0*4(x2)

	getq x1, q2
	sw x1,   1*4(x2)

	getq x1, q3
	sw x1,   2*4(x2)

	sw x3,   3*4(x2)
	sw x4,   4*4(x2)
	sw x5,   5*4(x2)
	sw x6,   6*4(x2)
	sw x7,   7*4(x2)
	sw x8,   8*4(x2)
	sw x9,   9*4(x2)
	sw x10, 10*4(x2)
	sw x11, 11*4(x2)
	sw x12, 12*4(x2)
	sw x13, 13*4(x2)
	sw x14, 14*4(x2)
	sw x15, 15*4(x2)
	sw x16, 16*4(x2)
	sw x17, 17*4(x2)
	sw x18, 18*4(x2)
	sw x19, 19*4(x2)
	sw x20, 20*4(x2)
	sw x21, 21*4(x2)
	sw x22, 22*4(x2)
	sw x23, 23*4(x2)
	sw x24, 24*4(x2)
	sw x25, 25*4(x2)
	sw x26, 26*4(x2)
	sw x27, 27*4(x2)
	sw x28, 28*4(x2)
	sw x29, 29*4(x2)
	sw x30, 30*4(x2)
	sw x31, 31*4(x2)

	/* call interrupt handler C function */

	// arg0 = interrupt type bitmask
	getq x10, q1

	// arg1 = pointer to stored registers
	mv x11, x2

	// load irq handler address to x1 (ra)
	lw x1, 8(x0)

	// call to C function
	beq x0, x1, 1f
	jalr x1, x1, 0
1:

	/* restore registers */

	lw x1,   0*4(x2)
	setq q0, x1

	lw x1,   1*4(x2)
	setq q1, x1

	lw x1,   2*4(x2)
	setq q2, x1

	lw x3,   3*4(x2)
	lw x4,   4*4(x2)
	lw x5,   5*4(x2)
	lw x6,   6*4(x2)
	lw x7,   7*4(x2)
	lw x8,   8*4(x2)
	lw x9,   9*4(x2)
	lw x10, 10*4(x2)
	lw x11, 11*4(x2)
	lw x12, 12*4(x2)
	lw x13, 13*4(x2)
	lw x14, 14*4(x2)
	lw x15, 15*4(x2)
	lw x16, 16*4(x2)
	lw x17, 17*4(x2)
	lw x18, 18*4(x2)
	lw x19, 19*4(x2)
	lw x20, 20*4(x2)
	lw x21, 21*4(x2)
	lw x22, 22*4(x2)
	lw x23, 23*4(x2)
	lw x24, 24*4(x2)
	lw x25, 25*4(x2)
	lw x26, 26*4(x2)
	lw x27, 27*4(x2)
	lw x28, 28*4(x2)
	lw x29, 29*4(x2)
	lw x30, 30*4(x2)
	lw x31, 31*4(x2)

	getq x1, q1
	getq x2, q2

	retirq


start:
	/* zero-initialize all registers */
	addi x1, zero, 0
	addi x2, zero, 0
	addi x3, zero, 0
	addi x4, zero, 0
	addi x5, zero, 0
	addi x6, zero, 0
	addi x7, zero, 0
	addi x8, zero, 0
	addi x9, zero, 0
	addi x10, zero, 0
	addi x11, zero, 0
	addi x12, zero, 0
	addi x13, zero, 0
	addi x14, zero, 0
	addi x15, zero, 0
	addi x16, zero, 0
	addi x17, zero, 0
	addi x18, zero, 0
	addi x19, zero, 0
	addi x20, zero, 0
	addi x21, zero, 0
	addi x22, zero, 0
	addi x23, zero, 0
	addi x24, zero, 0
	addi x25, zero, 0
	addi x26, zero, 0
	addi x27, zero, 0
	addi x28, zero, 0
	addi x29, zero, 0
	addi x30, zero, 0
	addi x31, zero, 0

	/* set stack pointer */
	lui sp, %hi(4096)
	addi sp, sp, %lo(4096)

	/* call main */
	jal ra, main

	/* reset stack pointer */
	lui sp, %hi((64+128)*1024)
	addi sp, sp, %lo((64+128)*1024)

	/* jump to application */
#ifdef FLASHPMEM
	j 0x100000
#else
	j 0x10000
#endif

