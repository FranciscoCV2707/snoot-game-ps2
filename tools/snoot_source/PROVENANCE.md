# Exportador del fuente de Snoot Game

Este paquete lee `E:/snoot/snootgame/game`, sus guiones `.rpy`, sus imágenes, fuentes y traducción española.
No lee el CD, bytecode, imágenes ni audio generado por el port de PS1. Sus salidas están aisladas en este proyecto.

El parser, el compilador VNB, el renderizador de recetas y las tablas portátiles se adaptaron de las herramientas
del autor en `snoot-ps1` (`c245b07`). Reutilizar su traducción de Ren'Py evita perder la lógica ya comprobada;
no significa reutilizar sus recursos reducidos. Se conserva el ABI VNB del intérprete C para comparar las rutas.
Se extrajeron las utilidades léxicas y las tablas necesarias, sin el ensamblado ISO ni los toolchains de PS1.

La conversión de imágenes y audio para PSP/Vita se genera desde los archivos originales. El perfil Vita genera
960x544 y compone las páginas del menú de título desde el arte original de Ren'Py, sin fallback a recursos de PS1.
Español es el único idioma y `persistent.lewd` se compila como verdadero.

`FUENTE.json` conserva el hash de cada archivo del árbol original usado como fuente (incluidos guiones, arte, audio,
fuentes y metadatos). Antes de empaquetar, `tools.snoot_source.package` vuelve a cotejar las rutas y los SHA-256 con
el árbol actual y rechaza builds obsoletos o mezclados con otra versión del juego.

El juego y los recursos originales conservan las licencias y créditos de Cavemanon incluidos en su repositorio.
