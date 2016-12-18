module top (input clk_100mhz, output reg led1, led2, led3);

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

	// Reset Generator

	reg [3:0] resetn_gen = 0;
	reg resetn;

	always @(posedge clk) begin
		resetn <= &resetn_gen;
		resetn_gen <= {resetn_gen, pll_locked};
	end

	// Simple Example Design

	localparam COUNTER_BITS = 13;

	reg [COUNTER_BITS-1:0] counter;
	reg [COUNTER_BITS-1:0] counter_led1;
	reg [COUNTER_BITS-1:0] counter_led2;
	reg [COUNTER_BITS-1:0] counter_led3;

	reg [COUNTER_BITS:0] state_led1;
	reg [COUNTER_BITS:0] state_led2;
	reg [COUNTER_BITS:0] state_led3;

	always @(posedge clk) begin
		if (!resetn) begin
			counter <= 0;
			state_led1 <= 0;
			state_led2 <= 0;
			state_led3 <= 0;
		end else begin
			counter <= counter + 1;
			state_led1 <= state_led1 + !counter;
			state_led2 <= state_led1 + ((2 << COUNTER_BITS) / 3);
			state_led3 <= state_led1 + ((4 << COUNTER_BITS) / 3);
		end

		counter_led1 <= (state_led1[COUNTER_BITS] ? ((2 << COUNTER_BITS)-1) - state_led1 : state_led1);
		counter_led2 <= (state_led2[COUNTER_BITS] ? ((2 << COUNTER_BITS)-1) - state_led2 : state_led2);
		counter_led3 <= (state_led3[COUNTER_BITS] ? ((2 << COUNTER_BITS)-1) - state_led3 : state_led3);

		led1 <= (counter > counter_led1 + (1 << (COUNTER_BITS-1)));
		led2 <= (counter > counter_led2 + (1 << (COUNTER_BITS-1)));
		led3 <= (counter > counter_led3 + (1 << (COUNTER_BITS-1))) && !state_led3[2:0];
	end

endmodule
