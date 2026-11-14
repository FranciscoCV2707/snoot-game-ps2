#include "save.h"
#include "sdl_target.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#if defined(_EE)
#include <libmc.h>
#include "ps2_icon.h"
/* icon.sys y el icono 3D: sin ellos el navegador de la consola muestra la partida como "datos corruptos". */
static void ps2_mc_put(const char *name, const unsigned char *data, size_t size)
{
	char p[64];
	FILE *f;
	snprintf(p, sizeof(p), "mc0:/SNOOTGAME/%s", name);
	f = fopen(p, "rb");
	if (f) {
		/* Solo se reescribe si cambio (otra version del port): escribir en la tarjeta es lento. */
		static unsigned char old[sizeof(ps2_icon_icn)];
		size_t got = fread(old, 1, sizeof(old), f);
		int more = fgetc(f) != EOF;
		fclose(f);
		if (got == size && !more && !memcmp(old, data, size))
			return;
	}
	f = fopen(p, "wb");
	if (!f)
		return;
	fwrite(data, 1, size, f);
	fclose(f);
}
static void ps2_mc_icon(void)
{
	static int done;
	if (done)
		return;
	done = 1;
	ps2_mc_put("icon.sys", ps2_icon_sys, sizeof(ps2_icon_sys));
	ps2_mc_put(PS2_ICON_FILE, ps2_icon_icn, sizeof(ps2_icon_icn));
}
/* rom0:MCMAN no deja usar mc0: hasta que libmc detecta la tarjeta, y solo crea carpetas por su propia RPC. */
static int ps2_mc_ready(int create)
{
	static int started;
	int type = 0, free_kb = 0, format = 0, result = 0;
	static int reported;
	if (!started) {
		if (mcInit(MC_TYPE_MC) < 0)
			return 0;
		started = 1;
	}
	mcGetInfo(0, 0, &type, &free_kb, &format);
	mcSync(0, NULL, &result);
	if (!reported) {
		reported = 1;
		printf("save: PS2 mc0 result=%d type=%d free=%d format=%d\n", result, type, free_kb, format);
		fflush(stdout);
	}
	/* -1 = tarjeta recien detectada (valida); por debajo, no hay tarjeta. `format` solo lo rellena XMCSERV:
	 * con el MCSERV de la ROM una tarjeta sin formato se queda en el fallo de escritura. */
	if (result < -1 || type != MC_TYPE_PS2)
		return 0;
	if (create) {
		mcMkDir(0, 0, "/SNOOTGAME");
		mcSync(0, NULL, &result);
		ps2_mc_icon();
	}
	return 1;
}
#endif

static char dir[512] = SDL_TARGET_SAVE_DIR;
static unsigned seq;
static int last = -1;
static unsigned checksum(const uint8_t *p)
{
	unsigned s = 0x5a17;
	int i;
	for (i = SAVE_CONTROL_BYTES; i < SAVE_DATA_BYTES; i++)
		s = s * 33 + p[i];
	return s;
}
static void path(char *out, size_t n, int copy)
{
	const char *p = getenv("VN_SAVE_DIR");
	char base[512];
	if (p && *p)
		snprintf(dir, sizeof(dir), "%s", p);
	else if (SDL_TARGET_FIND_GAME_BASE(base, sizeof(base)))
		snprintf(dir, sizeof(dir), "%s/SAVE", base);
	snprintf(out, n, "%s/save%c.bin", dir, copy ? 'B' : 'A');
}
void save_set_icon(const uint8_t *p)
{
	(void)p;
}
static int readcopy(int copy, uint8_t *d, unsigned *number)
{
	char p[600];
	FILE *f;
	uint8_t block[SAVE_DATA_BYTES];
	unsigned saved, stored;
	path(p, sizeof(p), copy);
	f = fopen(p, "rb");
	if (!f)
		return -1;
	if (fread(block, 1, sizeof(block), f) != sizeof(block)) {
		fclose(f);
		return -1;
	}
	fclose(f);
	memcpy(&saved, block + 4, 4);
	memcpy(&stored, block + 8, 4);
	if (memcmp(block, "SNS1", 4) || checksum(block) != stored)
		return -1;
	*number = saved;
	memcpy(d, block, sizeof(block));
	return 0;
}
SaveResult save_read(uint8_t *d)
{
	char p[600];
	unsigned a = 0, b = 0;
	uint8_t other[SAVE_DATA_BYTES];
	int ra, rb;
#if defined(_EE)
	if (!getenv("VN_SAVE_DIR") && !strncmp(dir, "mc0:", 4) && !ps2_mc_ready(0))
		return SAVE_NO_CARD;
#endif
	path(p, sizeof(p), 0);
	ra = readcopy(0, d, &a);
	rb = readcopy(1, other, &b);
	if (ra && rb)
		return SAVE_NO_FILE;
	if (!rb && (ra || b > a)) {
		memcpy(d, other, sizeof(other));
		seq = b;
		last = 1;
	} else {
		seq = a;
		last = 0;
	}
	return SAVE_OK;
}
SaveResult save_write(uint8_t *d)
{
	char p[600], folder[600];
	FILE *f;
	int copy = last == 0 ? 1 : 0;
#if defined(_EE)
	if (!getenv("VN_SAVE_DIR") && !strncmp(dir, "mc0:", 4) && !ps2_mc_ready(1))
		return SAVE_NO_CARD;
#endif
	memcpy(d, "SNS1", 4);
	++seq;
	memcpy(d + 4, &seq, 4);
	{
		unsigned c = checksum(d);
		memcpy(d + 8, &c, 4);
		memset(d + 12, 0, 4);
	}
	path(p, sizeof(p), copy);
	snprintf(folder, sizeof(folder), "%s", p);
	{
		char *slash = strrchr(folder, '/');
		if (slash) {
			*slash = 0;
			make_dir(folder);
		}
	}
	f = fopen(p, "wb");
	if (!f)
		return SAVE_WRITE_ERROR;
	if (fwrite(d, 1, SAVE_DATA_BYTES, f) != SAVE_DATA_BYTES) {
		fclose(f);
		return SAVE_WRITE_ERROR;
	}
	fclose(f);
	last = copy;
	return SAVE_OK;
}
