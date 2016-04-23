#include <stdio.h>
#include <stdint.h>
#include "icosoc.h"

void update_leds()
{
	static uint32_t status = 1;
	*(volatile uint32_t*)0x20000000 = (status++) & 7;
}

void irq_handler(uint32_t irq_mask, uint32_t *regs)
{
	// timer interrupt
	if (irq_mask & 1)
	{
		// run IRQ payload
		update_leds();

		// restart timer
		icosoc_timer(1000000);
	}

	// SBREAK, ILLINS, or BUSERROR
	if (irq_mask & 6)
	{
		printf("System error!\n");
		icosoc_sbreak();
	}
}

int main()
{
	// register IRQ handler
	icosoc_irq(irq_handler);

	// enable IRQs
	icosoc_maskirq(0);

	// start timer
	icosoc_timer(1000000);

#if 0
	// calling sbreak will print "System error!"
	icosoc_sbreak();
#endif

	while (1) { }
}

