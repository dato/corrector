#!/usr/bin/env python3.6

"""Worker para el corrector automático.

El script:

  • recibe por entrada estándar un archivo en formato TAR con todos los
    archivos de la corrección:

      ⁃ "orig": el código del alumno, tal y como se recibió
      ⁃ "skel": el código base del TP, incluyendo pruebas públicas
      ⁃ "priv": pruebas privadas al corrector

  • ejecuta el corrector especificado con --corrector e imprime el
    resultado por salida estándar.

  • si hubo errores de ejecución (no de corrección), termina con estado de
    salida distinto de cero.
"""

import argparse
import pathlib
import signal
import subprocess
import sys
import tarfile
import tempfile

from java import CorregirJava

class ErrorAlumno(Exception):
  pass


class CorregirV2:
  """Corrector compatible con la versión 2.

  Sobreescribe en la entrega del alumno los archivos del esqueleto,
  e invoca a make.
  """
  def __init__(self, path):
    path = pathlib.Path(path)
    orig = path / "orig"
    skel = path / "skel"
    badmake = {"makefile", "GNUmakefile"}.intersection(orig.iterdir())

    if badmake:
      name = badmake.pop()
      raise ErrorAlumno(f"archivo ‘{name}’ no aceptado; solo ‘Makefile’")

    for file in orig.iterdir():
      dest = skel / file.name
      if not dest.exists():
        file.rename(dest)

    self.cwd = skel

  def run(self):
    cmd = subprocess.run(["make"], cwd=self.cwd, stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    print("Todo OK" if cmd.returncode == 0 else "ERROR",
          cmd.stdout.decode("utf-8", "replace"), sep="\n\n", end="")


CORRECTORES = {
    "v2": CorregirV2,
    "java": CorregirJava,
}


def ejecutar(corrector, timeout):
  """Función principal del script.
  """
  with tempfile.TemporaryDirectory(prefix="corrector.") as tmpdir:
    # Usamos sys.stdin.buffer para leer en binario (sys.stdin es texto).
    # Asimismo, el modo ‘r|’ (en lugar de ‘r’) indica que fileobj no es
    # seekable.
    with tarfile.open(fileobj=sys.stdin.buffer, mode="r|") as tar:
      tar.extractall(tmpdir)

    # TODO: XXX use subprocess's own timeout param
    signal.alarm(timeout)
    try:
      corrector(tmpdir).run()
    except Timeout:
      raise ErrorAlumno("El proceso tardó más de {} segundos".format(timeout))
    finally:
      signal.alarm(0)


def main():
  parser = argparse.ArgumentParser()

  parser.add_argument("--timeout", type=int, default=120,
                      help="tiempo máximo de ejecución en segundos")

  parser.add_argument("--corrector", type=str, choices=list(CORRECTORES),
                      help="corrector (lenguaje) a usar", default="v2")

  args = parser.parse_args()
  try:
    ejecutar(CORRECTORES[args.corrector], args.timeout)
  except ErrorAlumno as ex:
    print("ERROR: {}.".format(ex))

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
  main()

# vi:et:sw=2
