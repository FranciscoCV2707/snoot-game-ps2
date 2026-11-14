/* stb_vorbis para PS2 y la lectura de archivos de audio (vease vorbis_stb.h).
 *
 * PS2Stream: un archivo de solo lectura que NO queda abierto. cdfs.irx, el sistema de archivos del disco (tambien
 * bajo OPL), admite 4 archivos abiertos a la vez y el audio tenia uno por voz (hasta 14): al quinto, "File
 * descriptor overflow" y el juego ya no podia cargar ni un capitulo. Cada flujo guarda su posicion y un bufer; cuando
 * se vacia abre el archivo, lee STREAM_BYTES y lo cierra. De paso stb_vorbis deja de leer byte a byte con fgetc,
 * que en PS2 toma y suelta un semaforo del kernel en cada llamada. */
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define STREAM_BYTES 32768 /* ~2,7 s de Vorbis o 0,74 s de PCM mono a 22 kHz por cada apertura */

/* platforms/sdl/cd.c: un solo hilo a la vez en el sistema de archivos */
void ps2_io_lock(void);
void ps2_io_unlock(void);

typedef struct PS2Stream {
	char path[96];
	long start, size; /* posicion en el archivo del primer byte del bufer; tamano del archivo */
	int count, at;
	unsigned char data[STREAM_BYTES];
} PS2Stream;

PS2Stream *ps2_stream_open(const char *path)
{
	PS2Stream *stream;
	FILE *file;

	if (strlen(path) >= sizeof(stream->path))
		return NULL;
	ps2_io_lock();
	file = fopen(path, "rb");
	if (!file) {
		ps2_io_unlock();
		return NULL;
	}
	stream = calloc(1, sizeof(*stream));
	if (stream && fseek(file, 0, SEEK_END) == 0) {
		strcpy(stream->path, path);
		stream->size = ftell(file);
	} else {
		free(stream);
		stream = NULL;
	}
	fclose(file);
	ps2_io_unlock();
	return stream;
}

void ps2_stream_close(PS2Stream *stream)
{
	free(stream);
}

static int stream_fill(PS2Stream *stream)
{
	FILE *file;

	stream->start += stream->count;
	stream->count = stream->at = 0;
	if (stream->start >= stream->size)
		return 0;
	ps2_io_lock();
	file = fopen(stream->path, "rb");
	if (file) {
		setvbuf(file, NULL, _IONBF, 0);
		if (fseek(file, stream->start, SEEK_SET) == 0)
			stream->count = (int)fread(stream->data, 1, sizeof(stream->data), file);
		fclose(file);
	}
	ps2_io_unlock();
	return stream->count > 0;
}

static int stream_getc(PS2Stream *stream)
{
	if (stream->at >= stream->count && !stream_fill(stream))
		return EOF;
	return stream->data[stream->at++];
}

size_t ps2_stream_read(void *out, size_t size, size_t items, PS2Stream *stream)
{
	size_t wanted = size * items, done = 0;

	while (done < wanted) {
		size_t part = (size_t)(stream->count - stream->at);
		if (!part) {
			if (!stream_fill(stream))
				break;
			continue;
		}
		if (part > wanted - done)
			part = wanted - done;
		memcpy((unsigned char *)out + done, stream->data + stream->at, part);
		stream->at += (int)part;
		done += part;
	}
	return size ? done / size : 0;
}

long ps2_stream_tell(PS2Stream *stream)
{
	return stream->start + stream->at;
}

int ps2_stream_seek(PS2Stream *stream, long offset, int whence)
{
	if (whence == SEEK_END)
		offset += stream->size;
	else if (whence == SEEK_CUR)
		offset += ps2_stream_tell(stream);
	if (offset < 0)
		return -1;
	if (offset >= stream->start && offset <= stream->start + stream->count) {
		stream->at = (int)(offset - stream->start);
		return 0;
	}
	stream->start = offset;
	stream->count = stream->at = 0;
	return 0;
}

/* Las tablas del MDCT son float: calcular cada seno en double por software costaba ~120 ms al abrir una pista. */
#define sin(x) ((double)sinf((float)(x)))
#define cos(x) ((double)cosf((float)(x)))
/* Sin la conversion "rapida" a entero, que suma un double por muestra. */
#define STB_VORBIS_NO_FAST_SCALED_FLOAT
#define STB_VORBIS_NO_PUSHDATA_API
#define FILE PS2Stream
#define fgetc stream_getc
#define fread ps2_stream_read
#define ftell ps2_stream_tell
#define fseek ps2_stream_seek
#define fopen(path, mode) ps2_stream_open(path)
#define fclose ps2_stream_close
#include "stb_vorbis.c"

stb_vorbis *ps2_stream_vorbis(PS2Stream *stream, const stb_vorbis_alloc *block, int *error)
{
	return stb_vorbis_open_file(stream, 0, error, block);
}
