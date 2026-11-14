# PS2 — Toolchain Docker

## Imagen Docker

- Imagen: `ps2dev/ps2dev@sha256:5476fdfbf34d35eb644fde0a6f6533fb554a4a8171ce53dad7cd1df6077dfb05`
- Etiqueta de origen: `ps2dev/ps2dev:latest`
- Digest: `sha256:5476fdfbf34d35eb644fde0a6f6533fb554a4a8171ce53dad7cd1df6077dfb05`
- Tamaño: ~1.05 GB
- Comprobar localmente:

```sh
docker pull ps2dev/ps2dev@sha256:5476fdfbf34d35eb644fde0a6f6533fb554a4a8171ce53dad7cd1df6077dfb05
docker inspect --format "{{index .RepoDigests 0}}" ps2dev/ps2dev:latest
```

## Toolchain incluido

- Compilador EE: `mips64r5900el-ps2-elf-gcc (GCC) 15.2.0` (`/usr/local/ps2dev/ee/bin/`).
- IOP: `mipsel-none-elf-gcc` en `/usr/local/ps2dev/iop/bin/`.
- `PS2SDK=/usr/local/ps2dev/ps2sdk`, `PS2DEV=/usr/local/ps2dev`, `GSKIT=/usr/local/ps2dev/gsKit`.
- SDL2 2.32.10 portado a PS2 en `/usr/local/ps2dev/ps2sdk/ports` (`sdl2.pc`); también `SDL2_image`, `SDL2_mixer`, `SDL2_ttf`.
- gsKit en `/usr/local/ps2dev/gsKit`.
- `make` **no** está en la imagen: instalarlo con `apk add --no-cache make` dentro del contenedor.
- No hay `pkg-config`; las rutas se ponen a mano (ver `Makefile`).

## Compilación del hello

Fuente: `platforms/ps2/hello/` (`main.c` + `Makefile`).

```sh
docker run --rm -v "${PWD}:/src" -w /src/platforms/ps2/hello \
  ps2dev/ps2dev@sha256:5476fdfbf34d35eb644fde0a6f6533fb554a4a8171ce53dad7cd1df6077dfb05 \
  sh -c "apk add --no-cache make >/tmp/apk.log 2>&1 && make"
```

En Windows (PowerShell):

```powershell
docker run --rm -v "E:/Dev/renpy-console-project:/src" -w /src/platforms/ps2/hello `
  ps2dev/ps2dev@sha256:5476fdfbf34d35eb644fde0a6f6533fb554a4a8171ce53dad7cd1df6077dfb05 `
  sh -c "apk add --no-cache make >/tmp/apk.log 2>&1 && make"
```

## Salida esperada

- `platforms/ps2/hello/hello.elf` (ejecutable ELF de PS2).

Salida real del build (recortada):

```
mips64r5900el-ps2-elf-gcc ... -c main.c -o main.o
mips64r5900el-ps2-elf-gcc -T.../linkfile -O2 -o hello.elf main.o \
  -L.../ee/lib ... -L.../ports/lib -L.../gsKit/lib \
  -lSDL2main -lSDL2 -lm -lpatches -lgskit -ldmakit -lps2_drivers
```

## Lo que se verificó

Solo se verificó que compila y enlaza en la imagen Docker indicada. No se ha ejecutado el `hello.elf` resultante en PCSX2 ni en hardware PS2.

## Snoot con recursos compilados desde el juego original

`python platforms/ps2/build.py` compila `build/ps2/snoot.elf` y genera o valida los recursos desde el fuente original
`E:\snoot\snootgame\game`. El perfil PS2 escribe `build/ps2-source/DATA/`; no lee ni copia el disco de `snoot-ps1`.
Para regenerar recursos explicitamente: `python platforms/ps2/build.py --rebuild-data`.

El perfil porta 40 unidades, espanol y `lewd=True`, con imagenes convertidas a 640x360, fuente a cuerpo 18,
107 OGG estereo para musica y 72 PCM mono para efectos/UI. `manifest.json` conserva hashes SHA-256 de los 1.620
archivos fuente para invalidar datos obsoletos. La vista de 16:9 queda centrada en la salida 640x448 (`VIEW_Y=44`);
el cache de imagenes y el decodificador de audio se describen en "Fluidez y lectura desde disco" (abajo).

El adapter de PCSX2 prepara `build/ps2/disc/` desde ese `DATA/` y anade el `AUTOTEST.BIN` de cada escenario. El ELF
accede a la carpeta hermana `disc/` por HostFS. La opcion **Host Filesystem** debe estar habilitada en PCSX2; el
perfil portable local la configura en `inis/PCSX2.ini` (`HostFs = true`). [HostFS en PCSX2](https://github.com/PCSX2/pcsx2/issues/10259).
La pantalla SDL conserva la salida 640x448. El backend comparte el nucleo C99 y SDL con los demas ports, pero el
bytecode y los recursos de juego se compilan desde Snoot Game para PC.

PCSX2 se inicia con `-portable -nogui -fastboot -elf <archivo> -logfile <archivo> -earlyconsolelog`. La documentacion
oficial indica que `-nogui` tambien activa batch, que `-elf` sustituye el ELF de arranque, y que `-logfile` guarda el
log de la aplicacion. La BIOS se selecciona mediante la configuracion portable ya instalada; el CLI de PCSX2 no
ofrece una opcion de ruta de BIOS. `-earlyconsolelog` envia los mensajes tempranos del emulador a la consola. [Opciones
de linea de comandos de PCSX2](https://pcsx2.net/docs/advanced/cli/).

El adapter combina el log de PCSX2 y su salida de consola y conserva las lineas `T|` (con la hora que PCSX2
antepone quitada). El `printf` del EE llega al log por la consola del EE (`EnableEEConsole = true`), verificado en
ejecucion. Al terminar el recorrido el juego imprime `VN_QUIT` y sale (`exit(0)`); el adapter ve la marca en el log y
cierra PCSX2 (`taskkill /T`) sin esperar el timeout.

## Arranque en PS2: SIF RPC antes del audio

Sin mas, `snoot.elf` se colgaba antes de escribir nada: `SDL_InitSubSystem(SDL_INIT_AUDIO)` ejecuta
`init_audio_driver()` de `ps2_drivers`, que carga `libsd.irx` y `audsrv.irx` por SIF y llama a `audsrv_init()`. Sin
`SifInitRpc(0)` previo la llamada RPC se queda esperando al IOP para siempre. `video_init` llama antes a
`SifInitRpc(0)`, `sbv_patch_enable_lmb()` y `sbv_patch_disable_prefix_check()`, la misma secuencia `prepare_IOP()` de
la muestra `wav_sample` de [ps2_drivers](https://github.com/fjtrujy/ps2_drivers) (la libreria se enlaza con
`-lps2_drivers` y `-lpatches`). Con eso el juego carga sus datos por `host:`.

`python -m tools.ctl run --target ps2 --scenario tests/scenarios/snoot-route-chapter_x2.yaml` dio `traces match` /
`PASS` desde los datos directos del fuente: 165 lineas de traza y cero `DRAW_MISS` con cache 24. PCSX2 emitio
`VN_QUIT`; el adapter lo cerro al terminar. Es una validacion de emulador, no de consola PS2 fisica.

## Problemas encontrados

- La imagen no trae `make` ni `pkg-config`: el `Makefile` fija las rutas de include/lib a mano y el comando de build instala `make` con `apk`.
- El enlazado necesita `-L$(PS2SDK)/ports/lib` y `-L$(PS2DEV)/gsKit/lib`; sin ellas falla con `cannot find -lSDL2` / `-lgskit`.
- `*.elf` ya está ignorado por `.gitignore`, así que no se sube el binario.
- PS2 selecciona el renderer acelerado `PS2 gsKit` de SDL con vsync. `video.c` conserva los tintes en escala GS
  (`128 = neutro`) y reduce la opacidad SDL (`255 = opaco`) a la escala GS (`128 = opaco`); pasar los valores SDL
  directamente duplicaba la modulación de color en la salida visible. PCSX2 puede seguir usando su renderer Vulkan.
- El audio de SDL2 para PS2 se colgaba sin `SifInitRpc`: ver la sección de arranque arriba.
- PCSX2 puede quedarse colgado en el arranque del host en la enumeración de mandos SDL (el log se corta tras
  `SDLInputSource: Using Controller DB from resources.`); al repetir la corrida funciona. El adapter lo detecta como
  timeout y deja el log para revisarlo.


## Guardado, mando y recorte (2026-11-12)

- Guardado: `mc0:/SNOOTGAME/saveA.bin|saveB.bin`. `input_init` carga `rom0:MCMAN` y `rom0:MCSERV`; `save.c` detecta la
  tarjeta con libmc (`mcGetInfo`/`mcSync`) y crea la carpeta con `mcMkDir`. Con el MCSERV de la ROM, `mc0:` no acepta
  `mkdir` por fio ni nada hasta esa deteccion. Los builds `--trace` no usan la tarjeta salvo
  `VN_PS2_EXTRA_FLAGS=-DVN_PS2_SAVE_MC`, para que un escenario no herede partidas del anterior.
- Mando: `ljoy_h/ljoy_v` solo valen en modo analogico (`mode >> 4 == 7`); en digital llegan a 0.
- Recorte de escena: `SDL_RenderSetClipRect` no se usa en PS2 (su scissor recorta el cuadro entero); `video_flip`
  pinta dos bandas negras tras las capas de escena. Las capturas `shot` del Test Lab salen negras en PS2
  (`SDL_RenderReadPixels` no esta soportado): para revisar a ojo hay que capturar la ventana de PCSX2.
- Audio: el hilo decodificador corre con prioridad `TIME_CRITICAL`; el kernel del EE no reparte tiempo entre hilos.

## Consola real: arranque, paquete, proporcion e icono (2026-11-12)

- Paquete: `python platforms/ps2/package.py` (tras el build sin `--trace`) deja `dist/ps2/usb/SNOOT/` (`snoot.elf` +
  `DATA/`) y `dist/ps2/SnootGame-PS2.iso` (`SYSTEM.CNF`, `SNOT_000.01`, `DATA/`).
- FreeMcBoot: copiar la carpeta `SNOOT` a la raiz de una memoria USB FAT32 y lanzar `mass:/SNOOT/snoot.elf` desde
  uLaunchELF. El ISO sirve para OPL o para grabarlo.
- Arranque (`ps2_boot` en `platforms/sdl/cd.c`): con `host:` (PCSX2 `-elf`) no cambia nada. En cualquier otro caso
  reinicia el IOP, carga fileXio y, segun de donde arranco, `cdfs` (datos en `cdfs:/DATA`) o USB/BDM (datos en la
  carpeta `DATA` junto al ELF, o `mass:/SNOOT/DATA`), esperando hasta 15 s a que el dispositivo responda.
  `-DVN_PS2_FORCE_CONSOLE` fuerza esa ruta tambien desde `host:`.
- Verificado en PCSX2 arrancando el ISO: reinicio del IOP, lectura por `cdfs`, mando y tarjeta con los modulos de
  `rom0:`, opciones y guardado. Con `-DVN_PS2_FORCE_CONSOLE` desde `host:` los modulos USB (usbd, BDM, FAT)
  cargan bien, pero no se logro montar una memoria virtual en PCSX2: leer de `mass:` solo queda probado en consola.
  Sin memoria, tras 15 s sigue con la raiz por defecto. Bateria final: 15/15 PASS (rutas 1-4, extras, teclado).
  Al arrancar el ISO, PCSX2 imprime ~96 `Bad Sector Count Error` mientras `cdfs` lee el directorio; despues no.
- Proporcion: las 448 lineas llenan una tele 4:3, asi que la escena 640x360 se dibuja comprimida a 336 lineas
  (`PS2_BAND_H`) con filtro lineal y medio pixel de desplazamiento (`PS2_HALF`; sin el, el GS muestrea el borde del
  texel y aparecen lineas de la VRAM vecina). Los menus a pantalla completa (640x448) no se escalan.
- Icono de la partida: `platforms/ps2/icon.py` genera `icon.sys` y `snoot.icn` (cuadro de dos caras con `icon.ico`
  del juego) dentro del ELF; `save.c` los escribe en `mc0:/SNOOTGAME` si faltan o cambiaron. Visto en el navegador
  de la BIOS (lista y detalle).
- Elecciones con los botones del juego (`snoot_psp_choice_draw`) y sprites con su alfa (`img_draw_ex_alpha_rot`),
  como en Vita. Teclado del 13D: la ayuda baja al hueco bajo el teclado (antes la tapaba el campo de texto).
- Audio a ritmo normal (589 lineas del capitulo 4, 530 s): `underrun=0`.

## Fluidez y lectura desde disco (2026-11-12, tercera parte)

Medido con la linea `perf:` de los builds de traza (ms de cada 60 cuadros, peor cuadro, VRAM pedida). 1000 ms = 60 fps.

- **Vorbis en float.** `libvorbis` calcula con `double` y el EE solo tiene FPU de precision simple (`__muldf3` por
  software): decodificar la musica se llevaba ~70 % de la CPU y todo el juego iba a tirones. Ahora decodifica
  `stb_vorbis` (`platforms/ps2/stb_vorbis.c`, dominio publico) a traves de `vorbis_stb.h`, que da a `audio_native.c`
  las funciones `ov_*` que usa. Detalles: memoria de un bloque fijo por flujo (sin `alloca`), hilo de decodificacion
  con 64 KB de pila (SDL da 6 KB), tablas del MDCT con `sinf/cosf` (abrir una pista bajo de 122 a 40 ms).
- **cdfs solo admite 4 archivos abiertos.** El audio tenia uno por voz (hasta 14) y desde disco u OPL salia
  `File descriptor overflow` y despues `capitulo N no disponible`. En la carpeta `host:` de PCSX2 no hay limite, asi que
  la bateria no lo veia. `PS2Stream` (`vorbis_stb.c`) abre, lee 32 KB y cierra; lo usan Vorbis, los PCM y el indice.
- **Abrir pistas sin retener el audio.** Desde disco abrir tarda 0,2-0,4 s; la pista se abre en una voz aparte
  (`open_before_lock`) y con el audio retenido solo se copia. `audio_update` no espera al decodificador
  (`decode_busy`; `SDL_TryLockMutex` del SDL de PS2 espera igual). Dos bloques precargados por pista.
- **Panoramicas (Pan).** El bitmap 565 se convierte una vez a ABGR1555 al cargar y la textura (1024x512, CT16)
  guarda mas imagen que la vista: solo se rellena cuando la vista sale de ella (`draw_big_ps2`). Antes convertia y
  subia la vista entera en cada cuadro (~110 ms por cuadro).
- **Cache de imagenes.** 48 entradas y 6 MiB de texturas (`SDL_TARGET_RES_BYTES`, cota real de gsKit en
  `img_memory_bound`), blando (`SDL_TARGET_RES_SOFT_BYTES`): pasado el presupuesto desaloja lo que no esta en
  pantalla y, si todo se dibuja, carga igual. Con 16 entradas fijas la cola de Fang (38 cuadros) releia cada cuadro.
- **Datos.** Los parches de video van en RGB565 (antes RGBA4444 expandido a CT32) y su rectangulo se escala segun el
  perfil (antes x4 fijo, el de PSP: en PS2 caian desplazados). Las capas giradas de un `layeredimage` llevan el
  relleno de `rotate_pad` de Ren'Py (las fotos del celular quedaban corridas). Esto ultimo cambia tambien los datos
  de PSP y Vita la proxima vez que se regeneren.

Pruebas: `isotest.py` (scratch) arma un ISO con el ELF de traza y un `AUTOTEST.BIN` y lo arranca como disco. Capitulo 1
a ritmo de juego desde ISO: ~60 fps, `underrun=0`, sin `File descriptor overflow`.

Bateria (16 escenarios, `build/ps2/battery.txt`): 15 `PASS` (teclado, capitulos x1-x10, rutas 1-4), `underrun=0`,
heap maximo 22,5 MB. `snoot-phone-scroll` da `FAIL` por un evento (288 de 289): es un guion de pulsaciones a cuadros
fijos y no se ha investigado si ya fallaba antes de estos cambios. Las rutas tuvieron un `DRAW_MISS` cada una, ligado
al `TLB Miss` de abajo; tras serializar el acceso a archivos (`ps2_io_lock`, cd.c) la ruta 2 repetida dio 0.

Pendiente conocido: con `host:` aparece a veces `TLB Miss` en `_request_end` (sifrpc.c) al cargar imagenes mientras
suena audio; ya pasaba con libvorbis y no aparecio en las corridas desde ISO (fileXio).

## Disolvencias sin copia de pantalla (2026-11-12, cuarta parte)

El renderer de PS2 no lee el framebuffer ni dibuja a textura, asi que las transiciones re-emiten los dibujos del
cuadro anterior. En cada disolvencia (cada cambio de expresion) eso dejaba ver el fondo a traves de los personajes
y, como la re-emision iba por `LAYER_FX` sin recorte, los pies asomaban en la banda negra de abajo.

- `ps2_dissolve_merge` (video.c) cruza los dos cuadros dibujo a dibujo, cada uno en su capa: lo que esta igual en
  los dos se dibuja una vez y opaco; lo nuevo entra con alfa p; lo viejo queda opaco debajo si algo nuevo de su capa
  lo tapa (otra expresion, otro fondo) y se va con alfa 1 - p si no tiene relevo. La caja y el texto viejos no se
  re-emiten cuando el cuadro nuevo trae caja.
- Los dibujos re-emitidos de capas de escena llevan `clipped` y se recortan a la vista (tambien en los fundidos).

Limite conocido: un personaje que cambia a una pose de silueta muy distinta conserva la silueta vieja hasta el final
de la disolvencia. Visto en el capitulo 5 a ritmo de juego; `chapter_x7` y `chapter_x9` siguen en `PASS`. La bateria
completa no se repitio tras este cambio.

