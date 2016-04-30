module icosoc_flashmem (
	input clk, resetn,

	input valid,
	output ready,
	input [23:0] addr,
	output [31:0] rdata,

	output spi_cs,
	output spi_sclk,
	output spi_mosi,
	input spi_miso
);
	assign ready = 1, rdata = 0;
	assign spi_cs = 1, spi_sclk = 1, spi_mosi = 1;
endmodule
