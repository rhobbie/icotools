#!/usr/bin/env python3

import sys, os, glob, importlib, re
from collections import defaultdict
from argparse import ArgumentParser

cmd = ArgumentParser ()
cmd.add_argument \
    ( "-c", "--no-clean-target"
    , help   = "Don't generate clean:: target, generate CLEAN variable"
    , action = 'store_true'
    )
opt = cmd.parse_args ()

basedir = os.path.dirname(sys.argv[0])
clock_freq_hz = 6000000

icosoc_mk = defaultdict(list)
icosoc_ys = defaultdict(list)
icosoc_pcf = defaultdict(list)
icosoc_v = defaultdict(list)
testbench = defaultdict(list)

icosoc_c = list()
icosoc_h = list()

mods = dict()
used_plocs = set()
used_modtypes = set()
iowires = set()
modvlog = set()

enable_compressed_isa = False

pmod_locs = [
    "D8 C7 C6 B3 A1 A2 B1 B2".split(),
    "A9 B9 A10 B10 A11 B11 A16 A15".split(),
    "T8 T7 T6 T5 T3 T2 T1 R2".split(),
    "R14 T14 T13 T11 T10 T9 T16 T15".split()
]

def make_pins(pname):
    ploc = None

    m = re.match(r"^pmod(\d+)_(\d+)$", pname)
    if m:
        pmod_num = int(m.group(1))
        pmod_idx = int(m.group(2))
        assert 1 <= pmod_num <= len(pmod_locs)
        assert (1 <= pmod_idx <= 4) or (7 <= pmod_idx <= 10)
        if pmod_idx <= 4:
            ploc = pmod_locs[pmod_num-1][pmod_idx-1]
        else:
            ploc = pmod_locs[pmod_num-1][pmod_idx-3]

    if re.match(r"^pmod\d+$", pname):
        return make_pins(pname + "_10") + make_pins(pname + "_9") + make_pins(pname + "_8") + make_pins(pname + "_7") + \
               make_pins(pname + "_4") + make_pins(pname + "_3") + make_pins(pname + "_2") + make_pins(pname + "_1")

    assert ploc is not None
    assert ploc not in used_plocs
    used_plocs.add(ploc)

    iowires.add(pname)
    icosoc_v["12-iopins"].append("    inout %s," % pname)
    icosoc_pcf["12-iopins"].append("set_io %s %s" % (pname, ploc))
    return [ pname ]

def parse_cfg(f):
    global enable_compressed_isa
    current_mod_name = None
    cm = None

    for line in f:
        line = line.split()

        if len(line) == 0 or line[0] == "#":
            continue

        if line[0] == "compressed_isa":
            assert len(line) == 1
            assert current_mod_name is None
            enable_compressed_isa = True
            continue

        if line[0] == "mod":
            assert len(line) == 3
            current_mod_name = line[2]
            cm = {
                "name": current_mod_name,
                "type": line[1],
                "addr": None,
                "conns": defaultdict(list),
                "params": dict()
            }
            assert current_mod_name not in mods
            mods[current_mod_name] = cm

            if line[1] not in used_modtypes:
                used_modtypes.add(line[1])
                icosoc_ys["12-readvlog"].append("read_verilog %s/mod_%s/mod_%s.v" % (basedir, line[1], line[1]))
                modvlog.add("%s/mod_%s/mod_%s.v" % (basedir, line[1], line[1]))
            continue

        if line[0] == "connect":
            assert len(line) >= 3
            assert current_mod_name is not None
            for pname in line[2:]:
                for pn in make_pins(pname):
                    cm["conns"][line[1]].append(pn)
            continue

        if line[0] == "param":
            assert len(line) == 3
            assert current_mod_name is not None
            cm["params"][line[1]] = line[2]
            continue

        if line[0] == "address":
            assert len(line) == 2
            assert current_mod_name is not None
            assert cm["addr"] is None
            cm["addr"] = line[1]
            continue

        print("Cfg error: %s" % line)
        assert None

with open("icosoc.cfg", "r") as f:
    parse_cfg(f)

icosoc_h.append("""
#ifndef ICOSOC_H
#define ICOSOC_H

#include <stdint.h>

#define ICOSOC_CLOCK_FREQ_HZ %d

static inline void icosoc_irq(void(*irq_handler)(uint32_t,uint32_t*)) {
    *((uint32_t*)8) = (uint32_t)irq_handler;
}

static inline uint32_t icosoc_maskirq(uint32_t mask) {
    asm volatile ("custom0 %%0,%%0,0,3" : "+r" (mask) : : "memory");
    return mask;
}

static inline uint32_t icosoc_timer(uint32_t ticks) {
    asm volatile ("custom0 %%0,%%0,0,5" : "+r" (ticks));
    return ticks;
}

static inline void icosoc_sbreak() {
    asm volatile ("sbreak" : : : "memory");
}
""" % clock_freq_hz);

icosoc_c.append("""
#include "icosoc.h"
#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>

""");

icosoc_v["20-clockgen"].append("""
    // -------------------------------
    // Clock Generator

    wire clk, resetn;
    reg clk90;

    `define POW2CLOCKDIV 1

    reg [`POW2CLOCKDIV:0] divided_clock = 'b0x;
    always @* divided_clock[0] = CLK12MHZ;

    genvar i;
    generate for (i = 1; i <= `POW2CLOCKDIV; i = i+1) begin
        always @(posedge divided_clock[i-1])
            divided_clock[i] <= !divided_clock[i];
    end endgenerate

    SB_GB clock_buffer (
        .USER_SIGNAL_TO_GLOBAL_BUFFER(divided_clock[`POW2CLOCKDIV]),
        .GLOBAL_BUFFER_OUTPUT(clk)
    );

    always @(negedge divided_clock[`POW2CLOCKDIV-1])
        clk90 <= clk;

    // -------------------------------
    // Reset Generator

    reg [7:0] resetn_counter = 0;
    assign resetn = &resetn_counter;

    always @(posedge clk) begin
        if (!resetn)
            resetn_counter <= resetn_counter + 1;
    end
""")

icosoc_v["30-sramif"].append("""
    // -------------------------------
    // SRAM Interface

    reg [1:0] sram_state;
    reg sram_wrlb, sram_wrub;
    reg [15:0] sram_addr, sram_dout;
    wire [15:0] sram_din;

    SB_IO #(
        .PIN_TYPE(6'b 1010_01),
        .PULLUP(1'b 0)
    ) sram_io [15:0] (
        .PACKAGE_PIN({SRAM_D15, SRAM_D14, SRAM_D13, SRAM_D12, SRAM_D11, SRAM_D10, SRAM_D9, SRAM_D8,
                      SRAM_D7, SRAM_D6, SRAM_D5, SRAM_D4, SRAM_D3, SRAM_D2, SRAM_D1, SRAM_D0}),
        .OUTPUT_ENABLE(sram_wrlb || sram_wrub),
        .D_OUT_0(sram_dout),
        .D_IN_0(sram_din)
    );

    assign {SRAM_A15, SRAM_A14, SRAM_A13, SRAM_A12, SRAM_A11, SRAM_A10, SRAM_A9, SRAM_A8,
            SRAM_A7, SRAM_A6, SRAM_A5, SRAM_A4, SRAM_A3, SRAM_A2, SRAM_A1, SRAM_A0} = sram_addr;

    assign SRAM_CE = 0;
    assign SRAM_WE = (sram_wrlb || sram_wrub) ? !clk90 : 1;
    assign SRAM_OE = (sram_wrlb || sram_wrub);
    assign SRAM_LB = (sram_wrlb || sram_wrub) ? !sram_wrlb : 0;
    assign SRAM_UB = (sram_wrlb || sram_wrub) ? !sram_wrub : 0;
""")

icosoc_v["30-raspif"].append("""
    // -------------------------------
    // RasPi Interface

    wire recv_sync;

    // recv ep0: transmission test
    wire recv_ep0_valid;
    wire recv_ep0_ready;
    wire [7:0] recv_ep0_data;

    // recv ep1: firmware upload
    wire recv_ep1_valid;
    wire recv_ep1_ready = 1;
    wire [7:0] recv_ep1_data = recv_ep0_data;

    // recv ep2: console input
    wire recv_ep2_valid;
    reg  recv_ep2_ready;
    wire [7:0] recv_ep2_data = recv_ep0_data;

    // recv ep3: unused
    wire recv_ep3_valid;
    wire recv_ep3_ready = 1;
    wire [7:0] recv_ep3_data = recv_ep0_data;

    // send ep0: transmission test
    wire send_ep0_valid;
    wire send_ep0_ready;
    wire [7:0] send_ep0_data;

    // send ep1: debugger
    wire send_ep1_valid;
    wire send_ep1_ready;
    wire [7:0] send_ep1_data;

    // send ep2: console output
    reg  send_ep2_valid;
    wire send_ep2_ready;
    reg  [7:0] send_ep2_data;

    // send ep3: unused
    wire send_ep3_valid = 0;
    wire send_ep3_ready;
    wire [7:0] send_ep3_data = 'bx;

    // trigger lines
    wire trigger_0;  // debugger
    wire trigger_1;  // unused
    wire trigger_2;  // unused
    wire trigger_3;  // unused

    icosoc_raspif #(
        .NUM_RECV_EP(4),
        .NUM_SEND_EP(4),
        .NUM_TRIGGERS(4)
    ) raspi_interface (
        .clk(clk),
        .sync(recv_sync),

        .recv_valid({
            recv_ep3_valid,
            recv_ep2_valid,
            recv_ep1_valid,
            recv_ep0_valid
        }),
        .recv_ready({
            recv_ep3_ready,
            recv_ep2_ready,
            recv_ep1_ready,
            recv_ep0_ready
        }),
        .recv_tdata(
            recv_ep0_data
        ),

        .send_valid({
            send_ep3_valid,
            send_ep2_valid,
            send_ep1_valid,
            send_ep0_valid
        }),
        .send_ready({
            send_ep3_ready,
            send_ep2_ready,
            send_ep1_ready,
            send_ep0_ready
        }),
        .send_tdata(
            (send_ep3_data & {8{send_ep3_valid && send_ep3_ready}}) |
            (send_ep2_data & {8{send_ep2_valid && send_ep2_ready}}) |
            (send_ep1_data & {8{send_ep1_valid && send_ep1_ready}}) |
            (send_ep0_data & {8{send_ep0_valid && send_ep0_ready}})
        ),

        .trigger({
            trigger_3,
            trigger_2,
            trigger_1,
            trigger_0
        }),

        .RASPI_11(RASPI_11),
        .RASPI_12(RASPI_12),
        .RASPI_15(RASPI_15),
        .RASPI_16(RASPI_16),
        .RASPI_19(RASPI_19),
        .RASPI_21(RASPI_21),
        .RASPI_24(RASPI_24),
        .RASPI_35(RASPI_35),
        .RASPI_36(RASPI_36),
        .RASPI_38(RASPI_38),
        .RASPI_40(RASPI_40)
    );

    // -------------------------------
    // Transmission test (recv ep0, send ep0)

    assign send_ep0_data = ((recv_ep0_data << 5) + recv_ep0_data) ^ 7;
    assign send_ep0_valid = recv_ep0_valid;
    assign recv_ep0_ready = send_ep0_ready;

    // -------------------------------
    // Firmware upload (recv ep1)

    reg [15:0] prog_mem_addr;
    reg [31:0] prog_mem_data;
    reg [1:0] prog_mem_state;
    reg prog_mem_active = 0;
    reg prog_mem_reset = 0;

    always @(posedge clk) begin
        if (recv_sync) begin
            prog_mem_addr <= ~0;
            prog_mem_data <= 0;
            prog_mem_state <= 0;
            prog_mem_active <= 0;
            prog_mem_reset <= 0;
        end else
        if (recv_ep1_valid) begin
            prog_mem_addr <= prog_mem_addr + &prog_mem_state;
            prog_mem_data <= {recv_ep1_data, prog_mem_data[31:8]};
            prog_mem_state <= prog_mem_state + 1;
            prog_mem_active <= &prog_mem_state;
            prog_mem_reset <= 1;
        end
    end
""")

icosoc_v["40-cpu"].append("""
    // -------------------------------
    // PicoRV32 Core

    wire cpu_trap;
    wire mem_valid;
    wire mem_instr;
    wire [31:0] mem_addr;
    wire [31:0] mem_wdata;
    wire [3:0] mem_wstrb;

    reg mem_ready;
    reg [31:0] mem_rdata;

    wire resetn_picorv32 = resetn && !prog_mem_reset;

    picorv32 #(
        .COMPRESSED_ISA(%d),
        .ENABLE_IRQ(1)
    ) cpu (
        .clk       (clk            ),
        .resetn    (resetn_picorv32),
        .trap      (cpu_trap       ),
        .mem_valid (mem_valid      ),
        .mem_instr (mem_instr      ),
        .mem_ready (mem_ready      ),
        .mem_addr  (mem_addr       ),
        .mem_wdata (mem_wdata      ),
        .mem_wstrb (mem_wstrb      ),
        .mem_rdata (mem_rdata      ),
        .irq       (32'b0          )
    );
""" % (1 if enable_compressed_isa else 0))

icosoc_v["50-mods"].append("""
    // -------------------------------
    // IcoSoC Modules
""")

txt = icosoc_v["50-mods"]
for m in mods.values():
    if m["addr"] is not None:
        txt.append("    reg mod_%s_ctrl_wr;" % m["name"])
        txt.append("    reg mod_%s_ctrl_rd;" % m["name"])
        txt.append("    reg [ 7:0] mod_%s_ctrl_addr;" % m["name"])
        txt.append("    reg [31:0] mod_%s_ctrl_wdat;" % m["name"])
        txt.append("    wire [31:0] mod_%s_ctrl_rdat;" % m["name"])
        txt.append("    wire mod_%s_ctrl_done;" % m["name"])
        txt.append("")

    txt.append("    icosoc_mod_%s #(" % m["type"])
    for para_name, para_value in m["params"].items():
        txt.append("        .%s(%s)," % (para_name, para_value))
    for cn, cd in m["conns"].items():
        if cn != cn.upper(): continue
        txt.append("        .%s_LENGTH(%d)," % (cn, len(cd)))
    txt.append("        .CLOCK_FREQ_HZ(%d)" % clock_freq_hz)
    txt.append("    ) mod_%s (" % m["name"])
    txt.append("        .clk(clk),")
    txt.append("        .resetn(resetn),")

    if m["addr"] is not None:
        for n in "wr rd addr wdat rdat done".split():
            txt.append("        .ctrl_%s(mod_%s_ctrl_%s)," % (n, m["name"], n))

    for cn, cd in m["conns"].items():
        txt.append("        .%s({%s})," % (cn, ",".join(cd)))

    txt[-1] = txt[-1].rstrip(",")
    txt.append("    );")
    txt.append("")

    if m["addr"] is not None:
        if "71-bus-modinit" in icosoc_v:
            icosoc_v["71-bus-modinit"].append("");
        icosoc_v["71-bus-modinit"].append("        mod_%s_ctrl_wr <= 0;" % m["name"]);
        icosoc_v["71-bus-modinit"].append("        mod_%s_ctrl_rd <= 0;" % m["name"]);
        icosoc_v["71-bus-modinit"].append("        mod_%s_ctrl_addr <= mem_addr[15:0];" % m["name"]);
        icosoc_v["71-bus-modinit"].append("        mod_%s_ctrl_wdat <= mem_wdata;" % m["name"]);

        icosoc_v["73-bus-modwrite"].append("""
                        if (mem_addr[23:16] == %s) begin
                            mem_ready <= mod_%s_ctrl_done;
                            mod_%s_ctrl_wr <= !mod_%s_ctrl_done;
                        end
        """ % (m["addr"], m["name"], m["name"], m["name"]))

        icosoc_v["75-bus-modread"].append("""
                        if (mem_addr[23:16] == %s) begin
                            mem_ready <= mod_%s_ctrl_done;
                            mod_%s_ctrl_rd <= !mod_%s_ctrl_done;
                            mem_rdata <= mod_%s_ctrl_rdat;
                        end
        """ % (m["addr"], m["name"], m["name"], m["name"], m["name"]))

    if os.path.isfile("%s/mod_%s/mod_%s.py" % (basedir, m["type"], m["type"])):
        mod_loaded = importlib.import_module("mod_%s.mod_%s" % (m["type"], m["type"]))
        if hasattr(mod_loaded, "generate_c_code"):
            mod_loaded.generate_c_code(icosoc_h, icosoc_c, m)

icosoc_v["60-debug"].append("""
    // -------------------------------
    // On-chip logic analyzer (send ep1, trig1)

    wire debug_enable;
    wire debug_trigger;
    wire debug_triggered;
    wire [30:0] debug_data;

    icosoc_debugger #(
        .WIDTH(31),
        .DEPTH(256),
        .TRIGAT(192),
        .MODE("FREE_RUNNING")
    ) debugger (
        .clk(clk),
        .resetn(resetn),

        .enable(debug_enable),
        .trigger(debug_trigger),
        .triggered(debug_triggered),
        .data(debug_data),

        .dump_en(trigger_1),
        .dump_valid(send_ep1_valid),
        .dump_ready(send_ep1_ready),
        .dump_data(send_ep1_data)
    );

    assign debug_enable = 1;
    assign debug_trigger = 1;

    assign debug_data = {
        cpu_trap,          // debug_30 -> cpu_trap
        mem_wstrb[3],      // debug_29 -> mem_wstrb_3
        mem_wstrb[2],      // debug_28 -> mem_wstrb_2
        mem_wstrb[1],      // debug_27 -> mem_wstrb_1
        mem_wstrb[0],      // debug_26 -> mem_wstrb_0
        mem_valid,         // debug_25 -> mem_valid
        mem_ready,         // debug_24 -> mem_ready
        mem_instr,         // debug_23 -> mem_instr
        mem_addr[31],      // debug_22 -> addr_31
        mem_addr[30],      // debug_21 -> addr_30
        mem_addr[29],      // debug_20 -> addr_29
        mem_addr[28],      // debug_19 -> addr_28
        |mem_addr[31:18],  // debug_18 -> addr_hi
        mem_addr[17],      // debug_17 -> addr_17
        mem_addr[16],      // debug_16 -> addr_16
        mem_addr[15],      // debug_15 -> addr_15
        mem_addr[14],      // debug_14 -> addr_14
        mem_addr[13],      // debug_13 -> addr_13
        mem_addr[12],      // debug_12 -> addr_12
        mem_addr[11],      // debug_11 -> addr_11
        mem_addr[10],      // debug_10 -> addr_10
        mem_addr[9],       // debug_9  -> addr_9
        mem_addr[8],       // debug_8  -> addr_8
        mem_addr[7],       // debug_7  -> addr_7
        mem_addr[6],       // debug_6  -> addr_6
        mem_addr[5],       // debug_5  -> addr_5
        mem_addr[4],       // debug_4  -> addr_4
        mem_addr[3],       // debug_3  -> addr_3
        mem_addr[2],       // debug_2  -> addr_2
        mem_addr[1],       // debug_1  -> addr_1
        mem_addr[0]        // debug_0  -> addr_0
    };
""")

icosoc_v["70-bus"].append("""
    // -------------------------------
    // Memory/IO Interface

    localparam BOOT_MEM_SIZE = 1024;
    reg [31:0] memory [0:BOOT_MEM_SIZE-1];
    initial $readmemh("firmware.hex", memory);

    reg [7:0] spiflash_data;
    reg [3:0] spiflash_state;

    always @(posedge clk) begin
        mem_ready <= 0;
        sram_state <= 0;
        sram_wrlb <= 0;
        sram_wrub <= 0;
        sram_addr <= 'bx;
        sram_dout <= 'bx;
""")

icosoc_v["72-bus"].append("""
        if (send_ep2_ready)
            send_ep2_valid <= 0;

        recv_ep2_ready <= 0;

        if (!resetn_picorv32) begin
            LED1 <= 0;
            LED2 <= 0;
            LED3 <= 0;

            SPI_FLASH_CS   <= 1;
            SPI_FLASH_SCLK <= 1;
            SPI_FLASH_MOSI <= 0;

            send_ep2_valid <= 0;
            spiflash_state <= 0;

            if (prog_mem_active) begin
                memory[prog_mem_addr] <= prog_mem_data;
            end
        end else
        if (mem_valid && !mem_ready) begin
            (* parallel_case *)
            case (1)
                (mem_addr >> 2) < BOOT_MEM_SIZE: begin
                    if (mem_wstrb) begin
                        if (mem_wstrb[0]) memory[mem_addr >> 2][ 7: 0] <= mem_wdata[ 7: 0];
                        if (mem_wstrb[1]) memory[mem_addr >> 2][15: 8] <= mem_wdata[15: 8];
                        if (mem_wstrb[2]) memory[mem_addr >> 2][23:16] <= mem_wdata[23:16];
                        if (mem_wstrb[3]) memory[mem_addr >> 2][31:24] <= mem_wdata[31:24];
                    end else begin
                        mem_rdata <= memory[mem_addr >> 2];
                    end
                    mem_ready <= 1;
                end
                (mem_addr & 32'hF000_0000) == 32'h0000_0000 && (mem_addr >> 2) >= BOOT_MEM_SIZE: begin
                    if (mem_wstrb) begin
                        (* parallel_case, full_case *)
                        case (sram_state)
                            0: begin
                                sram_addr <= {mem_addr >> 2, 1'b0};
                                sram_dout <= mem_wdata[15:0];
                                sram_wrlb <= mem_wstrb[0];
                                sram_wrub <= mem_wstrb[1];
                                sram_state <= 1;
                            end
                            1: begin
                                sram_addr <= {mem_addr >> 2, 1'b1};
                                sram_dout <= mem_wdata[31:16];
                                sram_wrlb <= mem_wstrb[2];
                                sram_wrub <= mem_wstrb[3];
                                sram_state <= 0;
                                mem_ready <= 1;
                            end
                        endcase
                    end else begin
                        (* parallel_case, full_case *)
                        case (sram_state)
                            0: begin
                                sram_addr <= {mem_addr >> 2, 1'b0};
                                sram_state <= 1;
                            end
                            1: begin
                                sram_addr <= {mem_addr >> 2, 1'b1};
                                mem_rdata[15:0] <= sram_din;
                                sram_state <= 2;
                            end
                            2: begin
                                mem_rdata[31:16] <= sram_din;
                                sram_state <= 0;
                                mem_ready <= 1;
                            end
                        endcase
                    end
                end
                (mem_addr & 32'hF000_0000) == 32'h2000_0000: begin
                    mem_ready <= 1;
                    mem_rdata <= 0;
                    if (mem_wstrb) begin
                        if (mem_addr[23:16] == 0) begin
                            if (mem_addr[7:0] == 8'h 00) {LED3, LED2, LED1} <= mem_wdata;
                            if (mem_addr[7:0] == 8'h 04) {SPI_FLASH_CS, SPI_FLASH_SCLK, SPI_FLASH_MOSI} <= mem_wdata[3:1];
                            if (mem_addr[7:0] == 8'h 08) begin
                                if (spiflash_state == 0) begin
                                    spiflash_data <= mem_wdata;
                                    SPI_FLASH_MOSI <= mem_wdata[7];
                                end else begin
                                    if (spiflash_state[0])
                                        spiflash_data <= {spiflash_data, SPI_FLASH_MISO};
                                    else
                                        SPI_FLASH_MOSI <= spiflash_data[7];
                                end
                                SPI_FLASH_SCLK <= spiflash_state[0];
                                mem_ready <= spiflash_state == 15;
                                spiflash_state <= spiflash_state + 1;
                            end
                        end
""")

icosoc_v["74-bus"].append("""
                    end else begin
                        if (mem_addr[23:16] == 0) begin
`ifdef TESTBENCH
                            if (mem_addr[7:0] == 8'h 00) mem_rdata <= {LED3, LED2, LED1} | 32'h8000_0000;
`else
                            if (mem_addr[7:0] == 8'h 00) mem_rdata <= {LED3, LED2, LED1};
`endif
                            if (mem_addr[7:0] == 8'h 04) mem_rdata <= {SPI_FLASH_CS, SPI_FLASH_SCLK, SPI_FLASH_MOSI, SPI_FLASH_MISO};
                            if (mem_addr[7:0] == 8'h 08) mem_rdata <= spiflash_data;
                        end
""")

icosoc_v["76-bus"].append("""
                    end
                end
                (mem_addr & 32'hF000_0000) == 32'h3000_0000: begin
                    if (mem_wstrb) begin
                        if (send_ep2_ready || !send_ep2_valid) begin
                            send_ep2_valid <= 1;
                            send_ep2_data <= mem_wdata;
                            mem_ready <= 1;
                        end
                    end else begin
                        if (recv_ep2_valid && !recv_ep2_ready) begin
                            recv_ep2_ready <= 1;
                            mem_rdata <= recv_ep2_data;
                        end else begin
                            mem_rdata <= ~0;
                        end
                        mem_ready <= 1;
                    end
                end
            endcase
        end
    end
""")

icosoc_v["10-moddecl"].append("module icosoc (")
icosoc_v["10-moddecl"].append("    input CLK12MHZ,")
icosoc_v["10-moddecl"].append("    output reg LED1, LED2, LED3,")
icosoc_v["10-moddecl"].append("")

iowires |= set("CLK12MHZ LED1 LED2 LED3".split())

icosoc_v["12-iopins"].append("")

icosoc_v["15-moddecl"].append("    output reg SPI_FLASH_CS,")
icosoc_v["15-moddecl"].append("    output reg SPI_FLASH_SCLK,")
icosoc_v["15-moddecl"].append("    output reg SPI_FLASH_MOSI,")
icosoc_v["15-moddecl"].append("    input      SPI_FLASH_MISO,")
icosoc_v["15-moddecl"].append("")

iowires.add("SPI_FLASH_CS")
iowires.add("SPI_FLASH_SCLK")
iowires.add("SPI_FLASH_MOSI")
iowires.add("SPI_FLASH_MISO")

icosoc_v["15-moddecl"].append("    // RasPi Interface: 9 Data Lines (cmds have MSB set)")
icosoc_v["15-moddecl"].append("    inout RASPI_11, RASPI_12, RASPI_15, RASPI_16, RASPI_19, RASPI_21, RASPI_24, RASPI_35, RASPI_36,")
icosoc_v["15-moddecl"].append("")
icosoc_v["15-moddecl"].append("    // RasPi Interface: Control Lines")
icosoc_v["15-moddecl"].append("    input RASPI_38, RASPI_40,")
icosoc_v["15-moddecl"].append("")

iowires |= set("RASPI_11 RASPI_12 RASPI_15 RASPI_16 RASPI_19 RASPI_21 RASPI_24 RASPI_35 RASPI_36 RASPI_38 RASPI_40".split())

icosoc_v["15-moddecl"].append("    // SRAM Interface")
icosoc_v["15-moddecl"].append("    output SRAM_A0, SRAM_A1, SRAM_A2, SRAM_A3, SRAM_A4, SRAM_A5, SRAM_A6, SRAM_A7,")
icosoc_v["15-moddecl"].append("    output SRAM_A8, SRAM_A9, SRAM_A10, SRAM_A11, SRAM_A12, SRAM_A13, SRAM_A14, SRAM_A15,")
icosoc_v["15-moddecl"].append("    inout SRAM_D0, SRAM_D1, SRAM_D2, SRAM_D3, SRAM_D4, SRAM_D5, SRAM_D6, SRAM_D7,")
icosoc_v["15-moddecl"].append("    inout SRAM_D8, SRAM_D9, SRAM_D10, SRAM_D11, SRAM_D12, SRAM_D13, SRAM_D14, SRAM_D15,")
icosoc_v["15-moddecl"].append("    output SRAM_CE, SRAM_WE, SRAM_OE, SRAM_LB, SRAM_UB")
icosoc_v["15-moddecl"].append(");")

iowires |= set("SRAM_A0 SRAM_A1 SRAM_A2 SRAM_A3 SRAM_A4 SRAM_A5 SRAM_A6 SRAM_A7".split())
iowires |= set("SRAM_A8 SRAM_A9 SRAM_A10 SRAM_A11 SRAM_A12 SRAM_A13 SRAM_A14 SRAM_A15".split())
iowires |= set("SRAM_D0 SRAM_D1 SRAM_D2 SRAM_D3 SRAM_D4 SRAM_D5 SRAM_D6 SRAM_D7".split())
iowires |= set("SRAM_D8 SRAM_D9 SRAM_D10 SRAM_D11 SRAM_D12 SRAM_D13 SRAM_D14 SRAM_D15".split())
iowires |= set("SRAM_CE SRAM_WE SRAM_OE SRAM_LB SRAM_UB".split())

icosoc_v["95-endmod"].append("endmodule")

icosoc_pcf["10-std"].append("""
set_io CLK12MHZ R9

set_io LED1 C8
set_io LED2 F7
set_io LED3 K9

set_io SPI_FLASH_CS   R12
set_io SPI_FLASH_SCLK R11
set_io SPI_FLASH_MOSI P12
set_io SPI_FLASH_MISO P11

set_io RASPI_11 A5
set_io RASPI_12 F9
set_io RASPI_15 E9
set_io RASPI_16 E10
set_io RASPI_19 A6
set_io RASPI_21 A7
set_io RASPI_24 H6
set_io RASPI_35 D10
set_io RASPI_36 D9
set_io RASPI_38 C9
set_io RASPI_40 C10

set_io SRAM_A0  L7
set_io SRAM_A1  L5
set_io SRAM_A2  L6
set_io SRAM_A3  K3
set_io SRAM_A4  L4
set_io SRAM_A5  L3
set_io SRAM_A6  M4
set_io SRAM_A7  N4
set_io SRAM_A8  N3
set_io SRAM_A9  P6
set_io SRAM_A10 P4
set_io SRAM_A11 M1
set_io SRAM_A12 M2
set_io SRAM_A13 L1
set_io SRAM_A14 K1
set_io SRAM_A15 J2

set_io SRAM_D0  N2
set_io SRAM_D1  P1
set_io SRAM_D2  P2
set_io SRAM_D3  R1
set_io SRAM_D4  N5
set_io SRAM_D5  P7
set_io SRAM_D6  P5
set_io SRAM_D7  R4
set_io SRAM_D8  J4
set_io SRAM_D9  J3
set_io SRAM_D10 P8
set_io SRAM_D11 R6
set_io SRAM_D12 R5
set_io SRAM_D13 M8
set_io SRAM_D14 N7
set_io SRAM_D15 M7

set_io SRAM_CE  M3
set_io SRAM_WE  R3
set_io SRAM_OE  M5
set_io SRAM_LB  N6
set_io SRAM_UB  M6
""")

icosoc_mk["10-top"].append("")
icosoc_mk["10-top"].append("ifeq ($(shell which icoprog),)")
icosoc_mk["10-top"].append("SSH_RASPI := ssh pi@raspi")
icosoc_mk["10-top"].append("else")
icosoc_mk["10-top"].append("SSH_RASPI := sh -c")
icosoc_mk["10-top"].append("endif")
icosoc_mk["10-top"].append("")
icosoc_mk["10-top"].append("help:")
icosoc_mk["10-top"].append("\t@echo \"\"")
icosoc_mk["10-top"].append("\t@echo \"Building FPGA bitstream and program:\"")
icosoc_mk["10-top"].append("\t@echo \"   make prog_sram\"")
icosoc_mk["10-top"].append("\t@echo \"   make prog_flash\"")
icosoc_mk["10-top"].append("\t@echo \"\"")
icosoc_mk["10-top"].append("\t@echo \"Building firmware image and update:\"")
icosoc_mk["10-top"].append("\t@echo \"   make prog_firmware\"")
icosoc_mk["10-top"].append("\t@echo \"\"")
icosoc_mk["10-top"].append("\t@echo \"Resetting FPGA (prevent boot from flash):\"")
icosoc_mk["10-top"].append("\t@echo \"   make reset_halt\"")
icosoc_mk["10-top"].append("\t@echo \"\"")
icosoc_mk["10-top"].append("\t@echo \"Resetting FPGA (load image from flash):\"")
icosoc_mk["10-top"].append("\t@echo \"   make reset_boot\"")
icosoc_mk["10-top"].append("\t@echo \"\"")
icosoc_mk["10-top"].append("\t@echo \"Build and upload FPGA + application image:\"")
icosoc_mk["10-top"].append("\t@echo \"   make run\"")
icosoc_mk["10-top"].append("\t@echo \"\"")
icosoc_mk["10-top"].append("\t@echo \"Upload FPGA (no rebuild) + application image:\"")
icosoc_mk["10-top"].append("\t@echo \"   make softrun\"")
icosoc_mk["10-top"].append("\t@echo \"\"")
icosoc_mk["10-top"].append("\t@echo \"Console session (close with Ctrl-D):\"")
icosoc_mk["10-top"].append("\t@echo \"   make console\"")
icosoc_mk["10-top"].append("\t@echo \"\"")
icosoc_mk["10-top"].append("\t@echo \"Download debug trace (to 'debug.vcd'):\"")
icosoc_mk["10-top"].append("\t@echo \"   make debug\"")
icosoc_mk["10-top"].append("\t@echo \"\"")
icosoc_mk["10-top"].append("")
icosoc_mk["10-top"].append("prog_sram: icosoc.bin")
icosoc_mk["10-top"].append("\t$(SSH_RASPI) 'icoprog -p' < icosoc.bin")
icosoc_mk["10-top"].append("")
icosoc_mk["10-top"].append("prog_flash: icosoc.bin")
icosoc_mk["10-top"].append("\t$(SSH_RASPI) 'icoprog -f' < icosoc.bin")
icosoc_mk["10-top"].append("")
icosoc_mk["10-top"].append("prog_firmware: firmware.bin")
icosoc_mk["10-top"].append("\t$(SSH_RASPI) 'icoprog -w1' < firmware.bin")
icosoc_mk["10-top"].append("")
icosoc_mk["10-top"].append("reset_halt:")
icosoc_mk["10-top"].append("\t$(SSH_RASPI) 'icoprog -R'")
icosoc_mk["10-top"].append("")
icosoc_mk["10-top"].append("reset_boot:")
icosoc_mk["10-top"].append("\t$(SSH_RASPI) 'icoprog -b'")
icosoc_mk["10-top"].append("")
icosoc_mk["10-top"].append("run: icosoc.bin appimage.hex")
icosoc_mk["10-top"].append("\t$(SSH_RASPI) 'icoprog -p' < icosoc.bin")
icosoc_mk["10-top"].append("\t$(SSH_RASPI) 'icoprog -zZc2' < appimage.hex")
icosoc_mk["10-top"].append("")
icosoc_mk["10-top"].append("softrun: appimage.hex")
icosoc_mk["10-top"].append("\t$(SSH_RASPI) 'icoprog -p' < icosoc.bin")
icosoc_mk["10-top"].append("\t$(SSH_RASPI) 'icoprog -zZc2' < appimage.hex")
icosoc_mk["10-top"].append("")
icosoc_mk["10-top"].append("console:")
icosoc_mk["10-top"].append("\t$(SSH_RASPI) 'icoprog -c2'")
icosoc_mk["10-top"].append("")
icosoc_mk["10-top"].append("debug:")
icosoc_mk["10-top"].append("\tsedexpr=\"$$( grep '//.*debug_.*->' icosoc.v | sed 's,.*\(debug_\),s/\\1,; s, *-> *, /,; s, *$$, /;,;'; )\"; \\")
icosoc_mk["10-top"].append("\t\t\t$(SSH_RASPI) 'icoprog -V31' | sed -e \"$$sedexpr\" > debug.vcd")

icosoc_ys["10-readvlog"].append("read_verilog icosoc.v")
icosoc_ys["10-readvlog"].append("read_verilog %s/common/picorv32.v" % basedir)
icosoc_ys["10-readvlog"].append("read_verilog %s/common/icosoc_crossclkfifo.v" % basedir)
icosoc_ys["10-readvlog"].append("read_verilog %s/common/icosoc_debugger.v" % basedir)
icosoc_ys["10-readvlog"].append("read_verilog %s/common/icosoc_raspif.v" % basedir)
icosoc_ys["50-synthesis"].append("synth_ice40 -top icosoc -blif icosoc.blif")

icosoc_mk["50-synthesis"].append("icosoc.blif: icosoc.v icosoc.ys firmware.hex")
icosoc_mk["50-synthesis"].append("\tyosys -l icosoc.log -v3 icosoc.ys")

icosoc_mk["50-synthesis"].append("icosoc.asc: icosoc.blif icosoc.pcf")
icosoc_mk["50-synthesis"].append("\tset -x; for seed in 1234 2345 4567 5678 6789; do \\")
icosoc_mk["50-synthesis"].append("\tarachne-pnr -s $$seed -d 8k -p icosoc.pcf -o icosoc.asc icosoc.blif && exit 0; \\")
icosoc_mk["50-synthesis"].append("\tdone; false")

icosoc_mk["50-synthesis"].append("icosoc.bin: icosoc.asc")
icosoc_mk["50-synthesis"].append("\ticepack icosoc.asc icosoc.bin")

icosoc_mk["50-synthesis"].append("icosoc.rpt: icosoc.asc")
icosoc_mk["50-synthesis"].append("\ticetime -d hx8k -tr icosoc.rpt icosoc.asc")

tbfiles = set()
tbfiles.add("icosoc.v")
tbfiles.add("testbench.v")
tbfiles.add("%s/common/picorv32.v" % basedir)
tbfiles.add("%s/common/icosoc_crossclkfifo.v" % basedir)
tbfiles.add("%s/common/icosoc_debugger.v" % basedir)
tbfiles.add("%s/common/icosoc_raspif.v" % basedir)
tbfiles.add("%s/common/sim_sram.v" % basedir)
tbfiles.add("%s/common/sim_spiflash.v" % basedir)
tbfiles |= modvlog

icosoc_mk["60-simulation"].append("testbench: %s" % (" ".join(tbfiles)))
icosoc_mk["60-simulation"].append("\tiverilog -D TESTBENCH -o testbench %s $(shell yosys-config --datdir/ice40/cells_sim.v)" % (" ".join(tbfiles)))

icosoc_mk["60-simulation"].append("testbench_vcd: testbench firmware.hex")
icosoc_mk["60-simulation"].append("\tvvp -N testbench +vcd")

icosoc_mk["60-simulation"].append("testbench_novcd: testbench firmware.hex")
icosoc_mk["60-simulation"].append("\tvvp -N testbench")

icosoc_mk["70-firmware"].append("firmware.elf: %s/common/firmware.S %s/common/firmware.c %s/common/firmware.lds" % (basedir, basedir, basedir))
icosoc_mk["70-firmware"].append("\triscv32-unknown-elf-gcc -Os -m32 -march=RV32IXcustom -ffreestanding -nostdlib -Wall -o firmware.elf %s/common/firmware.S %s/common/firmware.c \\" % (basedir, basedir))
icosoc_mk["70-firmware"].append("\t\t\t--std=gnu99 -Wl,-Bstatic,-T,%s/common/firmware.lds,-Map,firmware.map,--strip-debug -lgcc" % basedir)
icosoc_mk["70-firmware"].append("\tchmod -x firmware.elf")

icosoc_mk["70-firmware"].append("firmware.bin: firmware.elf")
icosoc_mk["70-firmware"].append("\triscv32-unknown-elf-objcopy -O binary firmware.elf firmware.bin")
icosoc_mk["70-firmware"].append("\tchmod -x firmware.bin")

icosoc_mk["70-firmware"].append("firmware.hex: %s/common/makehex.py firmware.bin" % basedir)
icosoc_mk["70-firmware"].append("\tpython3 %s/common/makehex.py firmware.bin 1024 > firmware.hex" % basedir)
icosoc_mk["70-firmware"].append("\t@echo \"Firmware size: $$(grep .. firmware.hex | wc -l) / $$(wc -l < firmware.hex)\"")

icosoc_mk["90-extradeps"].append("icosoc.v: icosoc.mk")
icosoc_mk["90-extradeps"].append("icosoc.ys: icosoc.mk")
icosoc_mk["90-extradeps"].append("icosoc.pcf: icosoc.mk")
icosoc_mk["90-extradeps"].append("icosoc.mk: icosoc.cfg")
icosoc_mk["90-extradeps"].append("icosoc.mk: %s/icosoc.py" % basedir)
icosoc_mk["90-extradeps"].append("icosoc.mk: %s/mod_*/*" % basedir)
icosoc_mk["90-extradeps"].append("icosoc.blif: %s/common/*" % basedir)
icosoc_mk["90-extradeps"].append("icosoc.blif: %s/mod_*/*" % basedir)

filelist = [
    "firmware.bin firmware.elf firmware.hex firmware.map",
    "icosoc.mk icosoc.ys icosoc.pcf icosoc.v icosoc.h icosoc.c",
    "icosoc.blif icosoc.asc icosoc.bin icosoc.log icosoc.rpt debug.vcd",
    "testbench", "testbench.v", "testbench.vcd",
]

if opt.no_clean_target:
    l = "CLEAN ="
    for f in filelist:
        icosoc_mk["95-clean"].append(l + ' \\')
        l = '    ' + f
    icosoc_mk["95-clean"].append(l)
else:
    icosoc_mk["95-clean"].append("clean::")
    for f in filelist :
        icosoc_mk["95-clean"].append("\trm -f %s" % f)

if not opt.no_clean_target:
    icosoc_mk["99-special"].append(".PHONY: clean")
icosoc_mk["99-special"].append(".SECONDARY:")

icosoc_h.append("""
#endif /* ICOSOC_H */
""");

testbench["10-header"].append("""
module testbench;

    reg clk = 1;
    always #5 clk = ~clk;
""");

for net in sorted(iowires):
    testbench["20-ionets"].append("    wire %s;" % net)
testbench["20-ionets"].append("")

testbench["30-inst"].append("    icosoc uut (")
for net in sorted(iowires):
    testbench["30-inst"].append("        .%s(%s)," % (net, net))
testbench["30-inst"][-1] = testbench["30-inst"][-1].rstrip(",")
testbench["30-inst"].append("    );")
testbench["30-inst"].append("")

testbench["30-inst"].append("    sim_sram sram (")
for net in sorted(iowires):
    if net.startswith("SRAM_"):
        testbench["30-inst"].append("        .%s(%s)," % (net, net))
testbench["30-inst"][-1] = testbench["30-inst"][-1].rstrip(",")
testbench["30-inst"].append("    );")
testbench["30-inst"].append("")

testbench["30-inst"].append("    sim_spiflash spiflash (")
for net in sorted(iowires):
    if net.startswith("SPI_FLASH_"):
        testbench["30-inst"].append("        .%s(%s)," % (net, net))
testbench["30-inst"][-1] = testbench["30-inst"][-1].rstrip(",")
testbench["30-inst"].append("    );")
testbench["30-inst"].append("")

testbench["90-footer"].append("""
    assign CLK12MHZ = clk;

    wire [8:0] raspi_din;
    reg [8:0] raspi_dout = 9'b z_zzzz_zzzz;
    reg raspi_clk = 0;
    reg raspi_dir = 0;

    assign {RASPI_11, RASPI_12, RASPI_15, RASPI_16, RASPI_19, RASPI_21, RASPI_24, RASPI_35, RASPI_36} = raspi_dout;
    assign raspi_din = {RASPI_11, RASPI_12, RASPI_15, RASPI_16, RASPI_19, RASPI_21, RASPI_24, RASPI_35, RASPI_36};
    assign RASPI_40 = raspi_clk, RASPI_38 = raspi_dir;

    task raspi_send_word(input [8:0] data);
        begin
            raspi_clk <= 0;
            raspi_dir <= 1;
            raspi_dout <= {1'b0, data};

            repeat (5) @(posedge clk);
            raspi_clk <= 1;
            repeat (10) @(posedge clk);
            raspi_clk <= 0;
            repeat (5) @(posedge clk);
        end
    endtask

    task raspi_recv_word(output [8:0] data);
        begin
            raspi_clk <= 0;
            raspi_dir <= 0;
            raspi_dout <= 9'b z_zzzz_zzzz;

            repeat (5) @(posedge clk);
            raspi_clk <= 1;
            repeat (10) @(posedge clk);
            data = raspi_din;
            raspi_clk <= 0;
            repeat (5) @(posedge clk);
        end
    endtask

    reg [7:0] raspi_current_ep;
    reg [8:0] raspi_current_word;

    initial begin
        if ($test$plusargs("vcd")) begin
            $dumpfile("testbench.vcd");
            $dumpvars(0, testbench);
        end

        $display("-- Printing console messages --");
        forever begin
            raspi_recv_word(raspi_current_word);
            if (raspi_current_word[8]) begin
                raspi_current_ep = raspi_current_word[7:0];
            end else if (raspi_current_ep == 2) begin
                $write("%c", raspi_current_word[7:0]);
                $fflush();
            end
        end
    end

    initial begin:appimgage_init
        reg [7:0] appimage [0:16*1024*1024-1];
        integer i;

        $readmemh("appimage.hex", appimage);

        for (i = 0; i < 'h10000; i=i+1) begin
            sram.sram_memory[(i + 'h8000) % 'h10000][7:0] = appimage['h10000 + 2*i];
            sram.sram_memory[(i + 'h8000) % 'h10000][15:8] = appimage['h10000 + 2*i + 1];
        end
    end
endmodule
""");

with open(basedir + "/common/syscalls.c", "r") as f:
    for line in f: icosoc_c.append(line.rstrip())

def write_outfile_dict(filename, data, comment_start = None):
    with open(filename, "w") as f:
        if comment_start is not None:
            print("%s #### This file is auto-generated from icosoc.py. Do not edit! ####" % comment_start, file=f)
            print("", file=f)
        for section, lines in sorted(data.items()):
            if comment_start is not None:
                print("%s ++ %s ++" % (comment_start, section), file=f)
            for line in lines: print(line, file=f)

def write_outfile_list(filename, data, comment_start = None):
    with open(filename, "w") as f:
        if comment_start is not None:
            print("%s #### This file is auto-generated from icosoc.py. Do not edit! ####" % comment_start, file=f)
            print("", file=f)
        for line in data:
            print(line, file=f)

write_outfile_dict("icosoc.mk", icosoc_mk, "#")
write_outfile_dict("icosoc.ys", icosoc_ys, "#")
write_outfile_dict("icosoc.pcf", icosoc_pcf, "#")
write_outfile_dict("icosoc.v", icosoc_v, "//")
write_outfile_dict("testbench.v", testbench, "//")
write_outfile_list("icosoc.h", icosoc_h, "//")
write_outfile_list("icosoc.c", icosoc_c, "//")

