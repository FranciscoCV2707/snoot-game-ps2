/* La parte de vorbisfile que usa audio_native.c, sobre stb_vorbis. libvorbis calcula con double y el EE solo tiene
 * FPU de precision simple: cada operacion va por software y decodificar la musica se llevaba ~70 % de la CPU.
 * stb_vorbis decodifica con float. Su memoria sale de un bloque fijo por flujo: asi no usa alloca en la pila del
 * hilo de decodificacion. */
#pragma once
#include <stdio.h>
#include <stdlib.h>

#define STB_VORBIS_HEADER_ONLY
#include "stb_vorbis.c"

/* vorbis_stb.c: archivo de solo lectura que no queda abierto (cdfs solo admite 4 a la vez). */
typedef struct PS2Stream PS2Stream;
PS2Stream *ps2_stream_open(const char *path);
size_t ps2_stream_read(void *out, size_t size, size_t items, PS2Stream *stream);
long ps2_stream_tell(PS2Stream *stream);
int ps2_stream_seek(PS2Stream *stream, long offset, int whence);
void ps2_stream_close(PS2Stream *stream);
stb_vorbis *ps2_stream_vorbis(PS2Stream *stream, const stb_vorbis_alloc *block, int *error);

typedef long long ogg_int64_t;
typedef struct {
	int channels;
	long rate;
} vorbis_info;
typedef struct {
	stb_vorbis *decoder;
	PS2Stream *stream;
	char *memory;
	ogg_int64_t position; /* cuadros entregados desde el inicio */
	vorbis_info info;
} OggVorbis_File;

static int ov_fopen(const char *path, OggVorbis_File *file)
{
	static const int sizes[] = {192 * 1024, 320 * 1024, 512 * 1024};
	unsigned i;

	memset(file, 0, sizeof(*file));
	file->stream = ps2_stream_open(path);
	if (!file->stream)
		return -1;
	for (i = 0; i < sizeof(sizes) / sizeof(sizes[0]); i++) {
		stb_vorbis_alloc block;
		stb_vorbis_info info;
		int error = 0;

		file->memory = malloc((size_t)sizes[i]);
		if (!file->memory)
			break;
		ps2_stream_seek(file->stream, 0, SEEK_SET);
		block.alloc_buffer = file->memory;
		block.alloc_buffer_length_in_bytes = sizes[i];
		file->decoder = ps2_stream_vorbis(file->stream, &block, &error);
		if (file->decoder) {
			info = stb_vorbis_get_info(file->decoder);
			file->info.channels = info.channels;
			file->info.rate = (long)info.sample_rate;
			return 0;
		}
		free(file->memory);
		file->memory = NULL;
		if (error != VORBIS_outofmem)
			break;
	}
	ps2_stream_close(file->stream);
	file->stream = NULL;
	return -1;
}

static vorbis_info *ov_info(OggVorbis_File *file, int link)
{
	(void)link;
	return file->decoder ? &file->info : NULL;
}

static long ov_read(OggVorbis_File *file, char *buffer, int bytes, int big_endian, int word, int is_signed,
                    int *section)
{
	int frames = stb_vorbis_get_samples_short_interleaved(file->decoder, 2, (short *)buffer, bytes / 2);

	(void)big_endian;
	(void)word;
	(void)is_signed;
	(void)section;
	file->position += frames;
	return (long)frames * 4;
}

static int ov_pcm_seek(OggVorbis_File *file, ogg_int64_t position)
{
	if (!stb_vorbis_seek(file->decoder, (unsigned)position))
		return -1;
	file->position = position;
	return 0;
}

static ogg_int64_t ov_pcm_tell(OggVorbis_File *file)
{
	return file->position;
}

static ogg_int64_t ov_pcm_total(OggVorbis_File *file, int link)
{
	(void)link;
	return (ogg_int64_t)stb_vorbis_stream_length_in_samples(file->decoder);
}

static void ov_clear(OggVorbis_File *file)
{
	if (file->decoder)
		stb_vorbis_close(file->decoder);
	ps2_stream_close(file->stream);
	free(file->memory);
	memset(file, 0, sizeof(*file));
}
