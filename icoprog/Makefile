
USBMODE ?= 0
GPIOMODE ?= 0

ifeq ($(shell bash -c 'type -p icoprog'),)
SSH_RASPI ?= ssh pi@raspi
else
SSH_RASPI ?= sh -c
endif

ifeq ($(USBMODE),1)
icoprog: icoprog.cc
	gcc -o icoprog -Wall -Os icoprog.cc -D USBMODE -lftdi -lrt -lstdc++
else
ifeq ($(GPIOMODE),1)
icoprog: icoprog.cc
	gcc -o icoprog -Wall -Os icoprog.cc -D GPIOMODE -lrt -lstdc++
else
icoprog: icoprog.cc
	gcc -o icoprog -Wall -Os icoprog.cc -lgpiod -lrt -lstdc++
endif
endif

example.json: example.v
	yosys -p 'synth_ice40 -json example.json' example.v

example.asc: example.json example.pcf
	nextpnr-ice40 --hx8k --package ct256 --pcf example.pcf --asc example.asc --json example.json

example.bin: example.asc
	icetime -d hx8k -c 100 example.asc
	icepack example.asc example.bin

example_sram: example.bin
	$(SSH_RASPI) 'icoprog -p' < example.bin

example_flash: example.bin
	$(SSH_RASPI) 'icoprog -f' < example.bin
	$(SSH_RASPI) 'icoprog -b'

reset:
	$(SSH_RASPI) 'icoprog -f' < example.pcf
	$(SSH_RASPI) 'icoprog -b'

install: icoprog
	sudo install icoprog /usr/local/bin/
	sudo chmod u+s /usr/local/bin/icoprog

uninstall:
	sudo rm -f /usr/local/bin/icoprog

clean:
	rm -f icoprog example.json example.asc example.bin

.PHONY: example_sram example_flash reset install clean

