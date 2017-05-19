`include "defines.vh"

module top (
	`OUTPUT_PINS
	output led1, led2, led3,
	input clk_100mhz
);
	// Clock Generator

	wire clk_25mhz;
	wire pll_locked;

	SB_PLL40_PAD #(
		.FEEDBACK_PATH("SIMPLE"),
		.DELAY_ADJUSTMENT_MODE_FEEDBACK("FIXED"),
		.DELAY_ADJUSTMENT_MODE_RELATIVE("FIXED"),
		.PLLOUT_SELECT("GENCLK"),
		.FDA_FEEDBACK(4'b1111),
		.FDA_RELATIVE(4'b1111),
		.DIVR(4'b0000),
		.DIVF(7'b0000111),
		.DIVQ(3'b101),
		.FILTER_RANGE(3'b101)
	) pll (
		.PACKAGEPIN   (clk_100mhz),
		.PLLOUTGLOBAL (clk_25mhz ),
		.LOCK         (pll_locked),
		.BYPASS       (1'b0      ),
		.RESETB       (1'b1      )
	);

	wire clk = clk_25mhz;

	// Pattern ROM

	reg [`MEM_WIDTH-1:0] romtable [0:`MEM_DEPTH-1];
	reg [`MEM_WIDTH-1:0] romdata;
	reg [7:0] romaddr = 0;

	always @(posedge clk)
		romdata <= romtable[romaddr];
	
	assign `OUTPUT_EXPR = romdata;

	initial $readmemb("memdata.dat", romtable);

	// Prescaler for 9600 baud

	reg [11:0] prescaler = 0;

	always @(posedge clk) begin
		prescaler <= prescaler + 1;
		if (prescaler == 2604) begin
			prescaler <= 0;
			romaddr <= romaddr + 1;
		end
	end

	// Blink LEDs

	reg [22:0] led_prescaler = 0;
	reg [31:0] xorshift32rng_state = 0;

	function [31:0] xorshift32rng_next;
		input [31:0] old_state;
	begin
		xorshift32rng_next = old_state ^ (old_state << 13) ^ !old_state;
		xorshift32rng_next = xorshift32rng_next ^ (xorshift32rng_next >> 17);
		xorshift32rng_next = xorshift32rng_next ^ (xorshift32rng_next << 5);
	end endfunction

	always @(posedge clk) begin
		led_prescaler <= led_prescaler + 1;
		if (led_prescaler == 0) begin
			xorshift32rng_state <= xorshift32rng_next(xorshift32rng_state);
		end
	end

	assign led1 = xorshift32rng_state[0];
	assign led2 = xorshift32rng_state[1];
	assign led3 = xorshift32rng_state[2];
endmodule
