#!/bin/bash

set -ex

apt-get install -y build-essential clang bison flex libreadline-dev \
	gawk tcl-dev libffi-dev git mercurial graphviz   \
	xdot pkg-config python python3 libftdi-dev \
	autoconf automake autotools-dev curl libmpc-dev \
	libmpfr-dev libgmp-dev gawk build-essential bison \
	flex texinfo gperf libtool patchutils bc zlib1g-dev

bash build-icotools.sh
bash build-icestorm.sh
bash build-riscv.sh

git clone https://github.com/cliffordwolf/icotools.git $HOME/icotools
chown -R --reference=$HOME $HOME/icotools

tar --numeric-owner -C / -cvzf archive.tgz \
	/usr/local/{bin,share/arachne-pnr,share/icebox,share/yosys} \
	/opt/riscv32{i,ic,im,imc} $HOME/icotools

