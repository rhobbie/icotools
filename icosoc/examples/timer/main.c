#include <stdio.h>
#include <stdint.h>
#include "icosoc.h"

void update_leds()
{
	static uint32_t status = 1;
	*(volatile uint32_t*)0x20000000 = (status++) & 7;
}

void irq_handler(uint32_t irq_mask)
{
	// timer interrupt
	if (irq_mask & 1)
	{
		// run IRQ payload
		update_leds();

		// restart timer
		asm volatile ("custom0 x0,%0,0,5" : : "r" (1000000)); // timer zero, 1000000
	}
}

int main()
{
	// register IRQ handler
	register_irq_handler(irq_handler);

	// enable IRQs and start timer
	asm volatile ("custom0 x0,x0,0,3"); // maskirq zero, zero
	asm volatile ("custom0 x0,%0,0,5" : : "r" (1000000)); // timer zero, 1000000

	while (1) { }
}

