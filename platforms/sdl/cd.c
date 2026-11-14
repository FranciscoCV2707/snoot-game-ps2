#include "cd.h"
#include "audio.h"
#include "sdl_target.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

static char root[512] = SDL_TARGET_DATA_DIR;
static char filename[600];
volatile uint32_t cd_sync_vblanks, cd_wait_vblanks;
/* Raiz de datos ya resuelta (en PSP puede ser ef0: en una PSP Go). La declara extern quien la necesita:
 * cd.h es contrato y no lleva nada de rutas. */
const char *cd_root(void)
{
	return root;
}
#if defined(_EE)
#include <kernel.h>
#include <iopcontrol.h>
#include <iopheap.h>
#include <loadfile.h>
#include <stdbool.h>
#include <unistd.h>
#include <ps2_cdfs_driver.h>
#include <ps2_fileXio_driver.h>
#include <ps2_usb_driver.h>
static int ps2_data_at(const char *candidate)
{
	char path[600];
	FILE *f;
	snprintf(path, sizeof(path), "%s/FONT.BIN", candidate);
	f = fopen(path, "rb");
	if (!f)
		return 0;
	fclose(f);
	snprintf(root, sizeof(root), "%s", candidate);
	return 1;
}
/* Arranque en PS2. Desde PCSX2 (host:) los datos salen de host:disc y el IOP se deja como esta. En consola
 * (uLaunchELF/FreeMcBoot desde USB, o disco/ISO) el IOP trae los modulos del lanzador: se reinicia y se cargan
 * solo los controladores de donde estan los datos. La carpeta DATA va junto al ELF. */
void ps2_boot(void)
{
	static int done;
	char cwd[256] = "", beside[300];
	int tries, disc;
	size_t n;
	if (done)
		return;
	done = 1;
	if (!getcwd(cwd, sizeof(cwd)))
		cwd[0] = 0;
	SifInitRpc(0);
#ifndef VN_PS2_FORCE_CONSOLE
	if (!strncmp(cwd, "host", 4)) {
		sbv_patch_enable_lmb();
		sbv_patch_disable_prefix_check();
		return;
	}
#endif
	while (!SifIopReset("", 0)) {
	}
	while (!SifIopSync()) {
	}
	SifInitRpc(0);
	SifLoadFileInit();
	SifInitIopHeap();
	sbv_patch_enable_lmb();
	sbv_patch_disable_prefix_check();
	sbv_patch_fileio();
	init_fileXio_driver();
	disc = !strncmp(cwd, "cdrom", 5) || !strncmp(cwd, "cdfs", 4);
	if (disc)
		init_cdfs_driver();
	else
		init_usb_driver(true);
	n = strlen(cwd);
	while (n && (cwd[n - 1] == '/' || cwd[n - 1] == '\\'))
		cwd[--n] = 0;
	snprintf(beside, sizeof(beside), "%s/DATA", cwd);
	/* La memoria USB tarda unos segundos en enumerarse despues de reiniciar el IOP. */
	for (tries = 0; tries < 150; tries++) {
		if (disc ? ps2_data_at("cdfs:/DATA") : (ps2_data_at(beside) || ps2_data_at("mass:/SNOOT/DATA")))
			break;
		SDL_Delay(100);
	}
	printf("cd: PS2 arranque=%s datos=%s intentos=%d\n", cwd, root, tries);
	fflush(stdout);
}
#endif
static void psp_stage_shot_names(void)
{
#if defined(__PSP__)
	char path[600];
	FILE *f;
	snprintf(path, sizeof(path), "%s/shot_names.txt", root);
	f = fopen(path, "r");
	if (!f)
		return;
	{
		char names[256];
		if (fgets(names, sizeof(names), f)) {
			size_t l = strlen(names);
			if (l && names[l - 1] == '\n')
				names[l - 1] = 0;
			SDL_setenv("VN_SHOT_NAMES", names, 1);   /* setenv a secas no esta declarado con -std=c99 en el SDK */
		}
	}
	fclose(f);
#endif
}

int cd_init(void)
{
	const char *p = getenv("VN_DATA_DIR");
	char base[512];
	if (p && *p) {
		snprintf(root, sizeof(root), "%s", p);
		return 1;
	}
	if (SDL_TARGET_FIND_GAME_BASE(base, sizeof(base)))
		snprintf(root, sizeof(root), "%s/DATA", base);
#ifdef VN_TRACE
	printf("cd: raiz %s\n", root);
#endif
	/* Los nombres de los pasos `shot` del escenario vienen en un fichero al lado de los datos, como en Vita y 3DS.
	 * En PSP no se pueden pasar por variable de entorno antes de arrancar porque la raiz (ms0:, o ef0: en una Go)
	 * se resuelve aqui mismo; sin esto todas las capturas se llaman "shot.bmp" y la ultima pisa a las demas (T-633). */
	psp_stage_shot_names();
	return 1;
}
static void make_path(const char *path)
{
	const char *base = strrchr(path, '\\');
	const char *slash = strrchr(path, '/');
	int i;
	base = base ? base + 1 : path;
	if (slash && slash + 1 > base)
		base = slash + 1;
	snprintf(filename, sizeof(filename), "%s/%s", root, base);
	for (i = (int)strlen(root) + 1; filename[i]; i++)
		filename[i] = (char)toupper((unsigned char)filename[i]);
}
static int find_file(const char *p, int *lba, int *size)
{
	FILE *f;
	long n;
	make_path(p);
	f = fopen(filename, "rb");
	if (!f)
		return -1;
	fseek(f, 0, SEEK_END);
	n = ftell(f);
	fclose(f);
	if (lba)
		*lba = 0;
	if (size)
		*size = (int)n;
	return 0;
}
#if defined(_EE)
/* Un solo hilo a la vez en el sistema de archivos. El fio de `host:` no aguanta dos (TLB Miss en _request_end de
 * sifrpc.c y lecturas rotas) y el hilo de audio abre y cierra archivos todo el rato (PS2Stream, vorbis_stb.c). */
static int io_sema = -1;

void ps2_io_lock(void)
{
	if (io_sema < 0) { /* la primera llamada es del arranque, antes de crear el hilo de audio */
		ee_sema_t sema = {0};
		sema.init_count = sema.max_count = 1;
		io_sema = CreateSema(&sema);
	}
	WaitSema(io_sema);
}

void ps2_io_unlock(void)
{
	SignalSema(io_sema);
}
#else
#define ps2_io_lock()
#define ps2_io_unlock()
#endif

int cd_find(const char *p, int *lba, int *size)
{
	int found;

	ps2_io_lock();
	found = find_file(p, lba, size);
	ps2_io_unlock();
	return found;
}

static int read_file(const char *p, void *b, int cap)
{
	FILE *f;
	long n;
	make_path(p);
	f = fopen(filename, "rb");
	if (!f)
		return -1;
	fseek(f, 0, SEEK_END);
	n = ftell(f);
	rewind(f);
	if (n > cap || fread(b, 1, (size_t)n, f) != (size_t)n) {
		fclose(f);
		return -1;
	}
	fclose(f);
	return (int)n;
}
int cd_read_file(const char *p, void *b, int cap)
{
	int size;

	ps2_io_lock();
	size = read_file(p, b, cap);
	ps2_io_unlock();
	return size;
}
int cd_read_sectors(int l, int n, void *b)
{
	(void)l;
	(void)n;
	(void)b;
	return -1;
}
int cd_read_start(int o, int l, int n, void *b)
{
	(void)o;
	(void)l;
	(void)n;
	(void)b;
	return -1;
}
int cd_read_poll(int o)
{
	(void)o;
	return 0;
}
int cd_busy(void)
{
	return 0;
}
void cd_wait(void)
{
}
