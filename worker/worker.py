#!/usr/bin/env python3

"""Worker para el corrector automático de Algoritmos II.

El workflow es simple a propósito:

  - recibe un archivo tar por entrada estándar y lo desempaca en un directorio
    temporal

  - ejecuta `make` en el directorio temporal, con un timeout

Así, el worker necesita muy poca lógica y se puede ejecutar en un sistema
de sólo lectura.

Nota: si se llega al timeout, la función ejecutar() no mata a los procesos
hijos. Quien llame al worker debería encargarse, por ejemplo ejecutando al
worker dentro de Docker.
"""

import argparse
import atexit
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile


def ejecutar(timeout):
  """Función principal del script.
  """
  tmpdir = tempfile.mkdtemp(prefix="corrector.")
  atexit.register(shutil.rmtree, tmpdir)

  # Usamos sys.stdin.buffer para leer en binario (sys.stdin es texto). Asimismo,
  # el modo ‘r|’ (en lugar de ‘r’) indica que fileobj no es seekable.
  try:
    with tarfile.open(fileobj=sys.stdin.buffer, mode="r|") as tar:
      tar.extractall(tmpdir)
  except tarfile.TarError as ex:
    sys.stderr.write("Error al desempacar: {}\n".format(ex))
    return -1

  signal.alarm(timeout)
  try:
    return subprocess.call(["make"], cwd=tmpdir,
                           stdin=subprocess.DEVNULL)
  except Timeout:
    sys.stderr.write("El proceso tardó más de {} segundos\n".format(timeout))
    return 3
  finally:
    signal.alarm(0)


def main():
  parser = argparse.ArgumentParser()

  parser.add_argument("--timeout", type=int, default=120,
                      help="tiempo máximo de ejecución en segundos")

  args = parser.parse_args()

  return ejecutar(args.timeout)

##

class Timeout(Exception):
  """Excepción para nuestra implementación de timeouts.
  """

def raise_timeout(unused_signum, unused_frame):
  """Lanza nuestra excepción Timeout.
  """
  raise Timeout

signal.signal(signal.SIGALRM, raise_timeout)

##

if __name__ == "__main__":
  sys.exit(main())

# vi:et:sw=2
