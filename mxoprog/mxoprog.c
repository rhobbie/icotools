#include <time.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <termios.h>
#include <assert.h>
#include <sys/time.h>
#include <gpiod.h>
#include "libxsvf.h"

#define RPI_ICE_CLK      4 // PIN  7, GPIO.4
#define RPI_ICE_CDONE   27 // PIN 13, GPIO.27
#define RPI_ICE_MOSI     5 // PIN 29, GPIO.5
#define RPI_ICE_MISO     6 // PIN 31, GPIO.6
#define LOAD_FROM_FLASH 13 // PIN 33, GPIO.13
#define RPI_ICE_CRESET  26 // PIN 37, GPIO.26
#define RPI_ICE_CS       8 // PIN 24, CE0
#define RPI_ICE_SELECT  12 // PIN 32, GPIO.12

#define RASPI_D8  17 // PIN 11, GPIO.17
#define RASPI_D7  18 // PIN 12, GPIO.18
#define RASPI_D6  22 // PIN 15, GPIO.22
#define RASPI_D5  23 // PIN 16, GPIO.23
#define RASPI_D4  10 // PIN 19, MOSI
#define RASPI_D3   9 // PIN 21, MISO
#define RASPI_D2   7 // PIN 26, CE1
#define RASPI_D1  19 // PIN 35, GPIO.19
#define RASPI_D0  16 // PIN 36, GPIO.16
#define RASPI_DIR 20 // PIN 38, GPIO.20
#define RASPI_CLK 21 // PIN 40, GPIO.21

char *consumer;
struct gpiod_chip *chip;
struct gpiod_line *line_RPI_ICE_CLK;
struct gpiod_line *line_RPI_ICE_CDONE;
struct gpiod_line *line_RPI_ICE_MOSI;
struct gpiod_line *line_RPI_ICE_MISO;
struct gpiod_line *line_LOAD_FROM_FLASH;
struct gpiod_line *line_RPI_ICE_CRESET;
struct gpiod_line *line_RPI_ICE_CS;
struct gpiod_line *line_RPI_ICE_SELECT;

struct gpiod_line *line_RASPI_D8;
struct gpiod_line *line_RASPI_D7;
struct gpiod_line *line_RASPI_D6;
struct gpiod_line *line_RASPI_D5;
struct gpiod_line *line_RASPI_D4;
struct gpiod_line *line_RASPI_D3;
struct gpiod_line *line_RASPI_D2;
struct gpiod_line *line_RASPI_D1;
struct gpiod_line *line_RASPI_D0;
struct gpiod_line *line_RASPI_DIR;
struct gpiod_line *line_RASPI_CLK;

#define line_MACHXO2_TDO line_RPI_ICE_MISO
#define line_MACHXO2_TDI line_RPI_ICE_MOSI
#define line_MACHXO2_TCK line_RPI_ICE_CS
#define line_MACHXO2_TMS line_RPI_ICE_CLK

#define LOW 0
#define HIGH 1

static void io_tms(int val)
{
	gpiod_line_set_value(line_MACHXO2_TMS, val ? HIGH : LOW);
}

static void io_tdi(int val)
{
	gpiod_line_set_value(line_MACHXO2_TDI, val ? HIGH : LOW);
}

static void io_tck(int val)
{
	gpiod_line_set_value(line_MACHXO2_TCK, val ? HIGH : LOW);
}

static void io_sck(int val)
{
	/* not available */
}

static void io_trst(int val)
{
	/* not available */
}

static int io_tdo()
{
	return gpiod_line_get_value(line_MACHXO2_TDO) == HIGH ? 1 : 0;
}

static int h_setup(struct libxsvf_host *h)
{
	return 0;
}

static int h_shutdown(struct libxsvf_host *h)
{
	return 0;
}

static void h_udelay(struct libxsvf_host *h, long usecs, int tms, long num_tck)
{
	// printf("[DELAY:%ld, TMS:%d, NUM_TCK:%ld]\n", usecs, tms, num_tck);

	if (num_tck > 0)
	{
		struct timeval tv1, tv2;
		gettimeofday(&tv1, NULL);

		io_tms(tms);
		while (num_tck > 0) {
			io_tck(0);
			io_tck(1);
			num_tck--;
		}

		gettimeofday(&tv2, NULL);
		if (tv2.tv_sec > tv1.tv_sec) {
			usecs -= (1000000 - tv1.tv_usec) + (tv2.tv_sec - tv1.tv_sec - 1) * 1000000;
			tv1.tv_usec = 0;
		}
		usecs -= tv2.tv_usec - tv1.tv_usec;

		// printf("[DELAY_AFTER_TCK:%ld]\n", usecs > 0 ? usecs : 0);
	}

	if (usecs > 0) {
		usleep(usecs);
	}
}

static int h_getbyte(struct libxsvf_host *h)
{
	return fgetc(stdin);
}

static int h_pulse_tck(struct libxsvf_host *h, int tms, int tdi, int tdo, int rmask, int sync)
{
	io_tms(tms);

	if (tdi >= 0)
		io_tdi(tdi);

	io_tck(0);
	io_tck(1);

	int line_tdo = io_tdo();
	int rc = line_tdo >= 0 ? line_tdo : 0;

	if (tdo >= 0 && line_tdo >= 0) {
		if (tdo != line_tdo)
			rc = -1;
	}

	// printf("[TMS:%d, TDI:%d, TDO_ARG:%d, TDO_LINE:%d, RMASK:%d, RC:%d]\n", tms, tdi, tdo, line_tdo, rmask, rc);
	return rc;
}

static void h_pulse_sck(struct libxsvf_host *h)
{
	// printf("[SCK]\n");

	io_sck(0);
	io_sck(1);
}

static void h_set_trst(struct libxsvf_host *h, int v)
{
	// printf("[TRST:%d]\n", v);
	io_trst(v);
}

static int h_set_frequency(struct libxsvf_host *h, int v)
{
	printf("WARNING: Setting JTAG clock frequency to %d ignored!\n", v);
	return 0;
}

static void h_report_tapstate(struct libxsvf_host *h)
{
	// printf("[%s]\n", libxsvf_state2str(h->tap_state));
}

static void h_report_device(struct libxsvf_host *h, unsigned long idcode)
{
	printf("idcode=0x%08lx, revision=0x%01lx, part=0x%04lx, manufactor=0x%03lx\n", idcode,
			(idcode >> 28) & 0xf, (idcode >> 12) & 0xffff, (idcode >> 1) & 0x7ff);
}

static void h_report_status(struct libxsvf_host *h, const char *message)
{
	// printf("[STATUS] %s\n", message);
}

static void h_report_error(struct libxsvf_host *h, const char *file, int line, const char *message)
{
	printf("[%s:%d] %s\n", file, line, message);
}

static void *h_realloc(struct libxsvf_host *h, void *ptr, int size, enum libxsvf_mem which)
{
	return realloc(ptr, size);
}

static struct libxsvf_host h = {
	.udelay = h_udelay,
	.setup = h_setup,
	.shutdown = h_shutdown,
	.getbyte = h_getbyte,
	.pulse_tck = h_pulse_tck,
	.pulse_sck = h_pulse_sck,
	.set_trst = h_set_trst,
	.set_frequency = h_set_frequency,
	.report_tapstate = h_report_tapstate,
	.report_device = h_report_device,
	.report_status = h_report_status,
	.report_error = h_report_error,
	.realloc = h_realloc,
	.user_data = NULL
};

void reset_inout()
{
	line_RPI_ICE_CLK=gpiod_chip_get_line(chip,RPI_ICE_CLK);
	line_RPI_ICE_CDONE=gpiod_chip_get_line(chip,RPI_ICE_CDONE);
	line_RPI_ICE_MOSI=gpiod_chip_get_line(chip,RPI_ICE_MOSI);
	line_RPI_ICE_MISO=gpiod_chip_get_line(chip,RPI_ICE_MISO);
	line_LOAD_FROM_FLASH=gpiod_chip_get_line(chip,LOAD_FROM_FLASH);
	line_RPI_ICE_CRESET=gpiod_chip_get_line(chip,RPI_ICE_CRESET);
	line_RPI_ICE_CS=gpiod_chip_get_line(chip,RPI_ICE_CS);
	line_RPI_ICE_SELECT=gpiod_chip_get_line(chip,RPI_ICE_SELECT);

	line_RASPI_D8=gpiod_chip_get_line(chip,RASPI_D8);
	line_RASPI_D7=gpiod_chip_get_line(chip,RASPI_D7);
	line_RASPI_D6=gpiod_chip_get_line(chip,RASPI_D6);
	line_RASPI_D5=gpiod_chip_get_line(chip,RASPI_D5);
	line_RASPI_D4=gpiod_chip_get_line(chip,RASPI_D4);
	line_RASPI_D3=gpiod_chip_get_line(chip,RASPI_D3);
	line_RASPI_D2=gpiod_chip_get_line(chip,RASPI_D2);
	line_RASPI_D1=gpiod_chip_get_line(chip,RASPI_D1);
	line_RASPI_D0=gpiod_chip_get_line(chip,RASPI_D0);

	line_RASPI_DIR=gpiod_chip_get_line(chip,RASPI_DIR);
	line_RASPI_CLK=gpiod_chip_get_line(chip,RASPI_CLK);

	gpiod_line_request_input(line_RPI_ICE_CLK,     consumer);
	gpiod_line_request_input(line_RPI_ICE_CDONE,   consumer);
	gpiod_line_request_input(line_RPI_ICE_MOSI,    consumer);
	gpiod_line_request_input(line_RPI_ICE_MISO,    consumer);
	gpiod_line_request_input(line_LOAD_FROM_FLASH, consumer);
	gpiod_line_request_input(line_RPI_ICE_CRESET,  consumer);
	gpiod_line_request_input(line_RPI_ICE_CS,      consumer);
	gpiod_line_request_input(line_RPI_ICE_SELECT,  consumer);

	gpiod_line_request_input(line_RASPI_D8, consumer);
	gpiod_line_request_input(line_RASPI_D7, consumer);
	gpiod_line_request_input(line_RASPI_D6, consumer);
	gpiod_line_request_input(line_RASPI_D5, consumer);
	gpiod_line_request_input(line_RASPI_D4, consumer);
	gpiod_line_request_input(line_RASPI_D3, consumer);
	gpiod_line_request_input(line_RASPI_D2, consumer);
	gpiod_line_request_input(line_RASPI_D1, consumer);
	gpiod_line_request_input(line_RASPI_D0, consumer);

	gpiod_line_request_output(line_RASPI_DIR, consumer,LOW);
	gpiod_line_request_output(line_RASPI_CLK, consumer,LOW);

}

int main(int argc, char **argv)
{
	consumer=argv[0];
	chip = gpiod_chip_open("/dev/gpiochip0");
	reset_inout();

	gpiod_line_set_direction_output(line_MACHXO2_TDI,LOW);
	gpiod_line_set_direction_output(line_MACHXO2_TCK,LOW);
	gpiod_line_set_direction_output(line_MACHXO2_TMS,LOW);

	printf("Scanning...\n");
	if (libxsvf_play(&h, LIBXSVF_MODE_SCAN) < 0) {
		fprintf(stderr, "Error while scanning JTAG chain.\n");
		reset_inout();
		return 1;
	}

	printf("Programming (reading SVF from stdin)...\n");
	if (libxsvf_play(&h, LIBXSVF_MODE_SVF) < 0) {
		fprintf(stderr, "Error while playing SVF file.\n");
		reset_inout();
		return 1;
	}

	printf("DONE.\n");
	reset_inout();
	return 0;
}

