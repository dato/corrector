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
import os
import signal
import subprocess
import sys
import tarfile
import tempfile

from java import CorregirJava

class ErrorAlumno(Exception):
  pass


class ProcessGroup(subprocess.Popen):
  """Creates processes in a new session, and sends signals to it.
  """
  def __init__(self, *args, **kwargs):
    kwargs["start_new_session"] = True
    super().__init__(*args, **kwargs)

  def send_signal(self, sig):
    pgid = os.getpgid(self.pid)
    os.killpg(pgid, sig)


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

  def run(self, timeout):
    msg = "ERROR"
    cmd = ProcessGroup(["make"], cwd=self.cwd, stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
      output, _ = cmd.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
      cmd.kill()  # Will cleanup all children thanks to ProcessGroup above.
      msg = f"ERROR: El proceso tardó más de {timeout} segundos"
      output, _ = cmd.communicate()

    print("Todo OK" if cmd.returncode == 0 else msg,
          output.decode("utf-8", "replace"), sep="\n\n", end="")


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

    signal.alarm(int(timeout * 1.5))
    try:
      corrector(tmpdir).run(timeout)
    except Timeout:
      # Cada corrector debería comprobar el tiempo, pero este es un error
      # genérico de última instancia.
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
