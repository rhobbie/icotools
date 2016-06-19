#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include "icosoc.h"
#include "sprites.h"

int main()
{
	volatile uint32_t *videomem = (void*)(0x20000000 + 1 * 0x10000);

	setbuf(stdout, NULL);
	putchar(0);

	while (1)
	{
		for (int i = 0; i < 1024; i++)
			videomem[i] = sprite0[i];

		for (int i = 0; i < 1000000; i++)
			asm volatile ("");

		for (int i = 0; i < 1024; i++)
			videomem[i] = sprite1[i];

		for (int i = 0; i < 1000000; i++)
			asm volatile ("");

		for (int i = 0; i < 1024; i++)
			videomem[i] = sprite0[i];

		for (int i = 0; i < 1000000; i++)
			asm volatile ("");

		for (int i = 0; i < 1024; i++)
			videomem[i] = sprite2[i];

		for (int i = 0; i < 1000000; i++)
			asm volatile ("");
	}
}

