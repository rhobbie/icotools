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

	// display sprite0 on first panel
	for (int i = 0; i < 1024; i++)
		videomem[1024+i] = sprite0[i];

	// animate sprite1/sprite2 on second panel
	while (1)
	{
		for (int i = 0; i < 1024; i++)
			videomem[i] = sprite1[i];

		for (int i = 0; i < 1000000; i++)
			asm volatile ("");

		for (int i = 0; i < 1024; i++)
			videomem[i] = sprite2[i];

		for (int i = 0; i < 1000000; i++)
			asm volatile ("");
	}
}

