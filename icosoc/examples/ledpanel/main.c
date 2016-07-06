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

	for (int k = 0;; k++)
	{
		volatile uint32_t *panel0 = videomem;
		volatile uint32_t *panel1 = videomem;

		if (k % 2 == 0)
			panel0 += 1024;
		else
			panel1 += 1024;

		// statically display sprite0 on one panel
		for (int i = 0; i < 1024; i++)
			panel0[i] = sprite0[i];

		// animate sprite1/sprite2 on other panel
		for (int l = 0; l < 3; l++)
		{
			for (int i = 0; i < 1024; i++)
				panel1[i] = sprite1[i];

			for (int i = 0; i < 1000000; i++)
				asm volatile ("" ::: "memory");

			for (int i = 0; i < 1024; i++)
				panel1[i] = sprite2[i];

			for (int i = 0; i < 1000000; i++)
				asm volatile ("" ::: "memory");
		}
	}
}

