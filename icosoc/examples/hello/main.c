#include <stdio.h>
#include <stdint.h>
#include "icosoc.h"

int main()
{
	icosoc_leds_dir(0xffff);

	for (uint8_t i = 0;; i++)
	{
		printf("[%02x] Hello World!\n", i);

		char buffer[100];
		int buffer_len;

		buffer_len = snprintf(buffer, 100, "[%02x] Hello World!\r\n", i);
		icosoc_ser0_write(buffer, buffer_len);

		icosoc_leds_set(1 << (i % 16));

		for (int i = 0; i < 100000; i++)
			asm volatile ("");
	}
}

