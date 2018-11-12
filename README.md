Corrector automático
====================

Este es el código fuente del corrector automático.

Consiste de:

  - El corrector automático
  - El control de copias


## Corrector automático

Es un servicio `corrector.service` que ejecuta `fetchmail` e invoca al código fuente del corrector automático `corrector.py`.
Este programa de Python levanta un worker de Docker en dónde se ejecuta la corrección.

## Control de copias

Es un script en bash (`ojo_bionico.sh`) que invoca el script de [MOSS](https://theory.stanford.edu/~aiken/moss/): `moss.pl`.

## Instalación

  1. Instalar [Docker](https://docs.docker.com/engine/installation/).

  2. Editar el archivo netrc con la contraseña de la cuenta de correo de las cuales se buscan los mails, y el access token de GitHub.

  3. Ejecutar el script de instalación `install.sh`. Este programa:
      - Crea los usuarios y los grupos que se van a utilizar en caso de que no existan.
      - Compila el wrapper del worker de Docker en dónde se ejecuta la corrección.
      - Instala los scripts de corrección, el servicio de `fetchmail` y el wrapper compilado.
      - Baja una copia del repositorio de las entregas, que actualiza con cada email recibido.

    Todos estos parámetros son configurables desde el archivo `corrector.env`.

## Actualización de imagen de Docker

Para que los cambios realizados al worker tomen efecto, se debe actualizar la imagen local de Docker que utilizamos: 

  1. Pushear al repo los cambios realizados al worker.

  2. Correr `sudo docker pull algoritmosrw/corrector`. Comprobar que se actualizó la imagen en https://hub.docker.com/r/algoritmosrw/corrector/


En caso de querer recompilar la imagen manualmente:

  1. `cd repo/worker`.

  2. `docker build -t algoritmosrw/corrector .`.
