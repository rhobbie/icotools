CC = $(RISCV_TOOLS_PREFIX)gcc
CFLAGS = --std=gnu99 -Os -MD -Wall -march=$(MARCH) -mabi=ilp32
OBJS = main.o icosoc.o

default: help

appimage.hex:
	echo > appimage.hex

firmware.elf: firmware.c
	$(RISCV_TOOLS_PREFIX)gcc -Os -march=$(MARCH) -mabi=ilp32 -ffreestanding -nostdlib -Wall -o firmware.elf $(ICOSOC_ROOT)/common/firmware.S firmware.c \
		--std=gnu99 -Wl,-Bstatic,-T,$(ICOSOC_ROOT)/common/firmware.lds,-Map,firmware.map,--strip-debug -lgcc
	chmod -x firmware.elf

icosoc.mk: icosoc.cfg
	../../icosoc.py -f

clean::
	rm -f appimage.hex $(OBJS) *.d

include icosoc.mk
-include *.d

