#include <stdio.h>
#include <stdint.h>
#include "icosoc.h"

volatile uint8_t *ioshim_memory_bytes = (void*)0x20010000;
volatile uint16_t *ioshim_memory_words = (void*)0x20010000;
volatile uint32_t *ioshim_reg_reset = (void*)0x20011000;

// small iohim prog to store the value 23 in memory byte 42
uint16_t myprog[] = {
	0xc2fa, //   0: ldi r15 42
	0xc1d7, //   1: ldi r13 23
	0xf9df, //   2: st r13 r15
	0xe003, //   3: mystop: b mystop
	0x0000  //   4: nop
};

int main()
{
	setbuf(stdout, NULL);

	// make sure ioshim is in reset
	*ioshim_reg_reset = -1;

	ioshim_memory_bytes[42] = 99;
	printf("ioshim byte 42 before experiment: %d\n", ioshim_memory_bytes[42]);

	// upload ioshim program
	for (int i = 0; i < sizeof(myprog)/sizeof(uint16_t); i++)
		ioshim_memory_words[i] = myprog[i];

	// start ioshim at address 0
	*ioshim_reg_reset = 0;

	// wait a bit
	for (int i = 0; i < 10; i++)
		asm volatile ("");

	printf("ioshim byte 42 after experiment: %d\n", ioshim_memory_bytes[42]);
	return 0;
}

