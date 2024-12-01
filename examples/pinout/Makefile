
ifeq ($(shell bash -c 'type -p icoprog'),)
SSH_RASPI ?= ssh pi@raspi
else
SSH_RASPI ?= sh -c
endif

all: icopins.bin

prog: icopins.bin
	$(SSH_RASPI) 'icoprog -p' < icopins.bin

reset:
	$(SSH_RASPI) 'icoprog -R'

icopins.json: icopins.v memdata.dat defines.vh
	yosys -p 'synth_ice40 -top top -json icopins.json' icopins.v

icopins.asc: icopins.json icoboard.pcf
	nextpnr-ice40 --hx8k --package ct256 --pcf icoboard.pcf --asc icopins.asc --json icopins.json


icopins.bin: icopins.asc
	icetime -d hx8k -c 25 icopins.asc
	icepack icopins.asc icopins.bin

memdata.dat: generate.py
	python3 generate.py

defines.vh: memdata.dat

clean:
	rm -f icopins.json icopins.asc icopins.bin
	rm -f memdata.dat defines.vh

.PHONY: all prog reset clean

