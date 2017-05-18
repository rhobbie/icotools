
all: icezero.bin

prog: icezero.bin
	python ice_zero_prog.py icezero.bin

icezero.blif: icezero.v memdata.dat defines.vh
	yosys -p 'synth_ice40 -top top -blif icezero.blif' icezero.v

icezero.asc: icezero.blif icezero.pcf
	arachne-pnr -d 8k -P tq144:4k -p icezero.pcf -o icezero.asc icezero.blif

icezero.bin: icezero.asc
	icetime -d hx8k -c 25 icezero.asc
	icepack icezero.asc icezero.bin

memdata.dat: generate.py
	python3 generate.py

defines.vh: memdata.dat

clean:
	rm -f icezero.blif icezero.asc icezero.bin
	rm -f memdata.dat defines.vh

.PHONY: all prog reset clean

