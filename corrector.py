#!/usr/bin/env python3.6

"""Script principal del corrector automático de Algoritmos II.

Las entradas al script son:

  - stdin: mensaje de correo enviado por el alumno

  - SKEL_DIR: un directorio con los archivos “base” de cada TP, p. ej. las
    pruebas de la cátedra y los archivos .h

  - WORKER_BIN: el binario que compila la entrega y la corre con Valgrind

El workflow es:

  - del mensaje entrante se detecta el identificador del TP (‘tp0’, ‘pila’,
    etc.) y el ZIP con la entrega

  - se une la entrega con los archivos base, de tal manera que del ZIP se ignora
    cualquier archivo presente en la base

  - el resultado de esta unión se le pasa a WORKER_BIN por entrada estándar

Salida:

  - un mensaje al alumno con los resultados. Se envía desde GMAIL_ACCOUNT.

  - se guarda una copia de los archivos en DATA_DIR/<TP_ID>/<YYYY_CX>/<PADRON>.
"""

import base64
import datetime
import email
import email.message
import email.policy
import email.utils
import io
import mimetypes
import os
import pathlib
import re
import smtplib
import subprocess
import sys
import tarfile
import zipfile

import httplib2
import oauth2client.client

ROOT_DIR = pathlib.Path(os.environ["CORRECTOR_ROOT"])
SKEL_DIR = ROOT_DIR / os.environ["CORRECTOR_SKEL"]
DATA_DIR = ROOT_DIR / os.environ["CORRECTOR_TPS"]
WORKER_BIN = ROOT_DIR / os.environ["CORRECTOR_WORKER"]

MAX_ZIP_SIZE = 1024 * 1024  # 1 MiB
PADRON_REGEX = re.compile(r"\b(SP\d+|CBC\d+|\d{5,})\b")

GMAIL_ACCOUNT = os.environ.get("CORRECTOR_ACCOUNT")
CLIENT_ID = os.environ.get("CORRECTOR_OAUTH_CLIENT")
CLIENT_SECRET = os.environ.get("CORRECTOR_OAUTH_SECRET")

# Si OAUTH_REFRESH_TOKEN no está definido, el mail se imprime por pantalla y no
# se envía.
OAUTH_REFRESH_TOKEN = os.environ.get("CORRECTOR_REFRESH_TOKEN")

# Nunca respondemos a mail enviado por estas direcciones.
IGNORE_ADDRESSES = {
    GMAIL_ACCOUNT,                   # Mail de nosotros mismos.
    "no-reply@accounts.google.com",  # Notificaciones sobre la contraseña.
}


class ErrorInterno(Exception):
  """Excepción para cualquier error interno en el programa.
  """

class ErrorAlumno(Exception):
  """Excepción para cualquier error en la entrega.
  """


def main():
  """Función principal.

  El flujo de la corrección se corta lanzando excepciones ErrorAlumno.
  """
  os.umask(0o027)

  msg = email.message_from_binary_file(sys.stdin.buffer,
                                       policy=email.policy.default)
  try:
    procesar_entrega(msg)
  except ErrorAlumno as ex:
    send_reply(msg, "ERROR: {}.".format(ex))

  # TODO(dato): capturar ‘ErrorInterno’ y avisar.


def procesar_entrega(msg):
  """Recibe el mensaje del alumno y lanza el proceso de corrección.
  """
  _, addr_from = email.utils.parseaddr(msg["From"])

  if addr_from in IGNORE_ADDRESSES:
    sys.stderr.write("Ignorando email de {}\n".format(addr_from))
    return

  tp_id = guess_tp(msg["Subject"])
  padron = get_padron_str(msg["Subject"])
  zip_obj = find_zip(msg)

  skel_dir = SKEL_DIR / tp_id
  skel_files = set()

  # Lanzar ya el proceso worker para poder pasar su stdin a tarfile.open().
  worker = subprocess.Popen([WORKER_BIN],
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)

  tar = tarfile.open(fileobj=worker.stdin, mode="w|", dereference=True)

  # Añadir al archivo TAR la base del TP (skel_dir).
  for entry in os.scandir(skel_dir):
    if entry.is_file():
      path = pathlib.PurePath(entry.path)
      rel_path = path.relative_to(skel_dir)
      skel_files.add(rel_path)
      tar.add(path, rel_path)

  moss = Moss(DATA_DIR, tp_id, padron)

  # A continuación añadir los archivos de la entrega (ZIP).
  for path, zip_info in zip_walk(zip_obj):
    info = tarfile.TarInfo(path.as_posix())
    info.size = zip_info.file_size
    info.mtime = zip_datetime(zip_info).timestamp()
    info.type, info.mode = tarfile.REGTYPE, 0o644

    moss.save_data(path, zip_obj.read(zip_info))

    if path in skel_files:
      continue
    if path in {"makefile", "GNUmakefile"}:
      raise ErrorAlumno(
          "archivo ‘{}’ no aceptado; solo ‘Makefile’".format(path))

    tar.addfile(info, zip_obj.open(zip_info.filename))

  moss.flush()
  tar.close()

  stdout, _ = worker.communicate()
  output = stdout.decode("utf-8", errors="replace")
  retcode = worker.wait()

  send_reply(msg, "{}\n\n{}".format("Todo OK" if retcode == 0
                                    else "ERROR", output))


def guess_tp(subject):
  """Devuelve el identificador del TP de la entrega.

  Por ejemplo, ‘tp0’ o ‘pila’.
  """
  subj_words = [w.lower() for w in re.split(r"[^_\w]+", subject)]
  candidates = {p.name.lower(): p.name for p in SKEL_DIR.iterdir()}

  for word in subj_words:
    if word in candidates:
      return candidates[word]

  raise ErrorAlumno("no se encontró nombre del TP en el asunto")


def get_padron_str(subject):
  """Devuelve una cadena con el padrón, o padrones, de una entrega.

  En el caso de entregas conjuntas, se devuelve PADRÓN1_PADRÓN2, con
  PADRÓN1 < PADRÓN2.
  """
  subject = subject.replace(".", "")
  matches = PADRON_REGEX.findall(subject)

  if matches:
    return "_".join(sorted(matches))

  raise ErrorAlumno("no se encontró el número de padrón en el asunto")


def id_cursada():
  """Devuelve el identificador de la cursada según año y cuatrimestre.

  El identificador es del tipo ‘2015_2’ o ‘2016_1’, donde el segundo elemento
  indica el cuatrimestre.

  El cuatrimestre es:

    - 1 si la fecha es antes del 1 de agosto;
    - 2 si es igual o posterior.
  """
  today = datetime.datetime.today()
  cutoff = today.replace(month=8, day=1)
  return "{}_{}".format(today.year, 1 if today < cutoff else 2)


def find_zip(msg):
  """Busca un adjunto .zip en un mensaje y lo devuelve.

  Args:
    - msg: un objeto email.message.Message.

  Returns:
    - un objeto zipfile.ZipFile.
  """
  for part in msg.walk():
    if part.get_content_maintype() == "multipart":
      continue  # Multipart es una enclosure.

    filename = part.get_filename()
    content_type = part.get_content_type()

    if filename:
      extension = os.path.splitext(filename)[1]
    else:
      extension = mimetypes.guess_extension(content_type)

    if extension and extension.lower() == ".zip":
      zipbytes = part.get_payload(decode=True)
      if len(zipbytes) > MAX_ZIP_SIZE:
        raise ErrorAlumno(
            "archivo ZIP demasiado grande ({} bytes)".format(len(zipbytes)))
      try:
        return zipfile.ZipFile(io.BytesIO(zipbytes))
      except zipfile.BadZipFile as ex:
        raise ErrorAlumno("no se pudo abrir el archivo {} ({} bytes): {}"
                          .format(filename, len(zipbytes), ex))

  raise ErrorAlumno("no se encontró un archivo ZIP en el mensaje")


def zip_walk(zip_obj, strip_toplevel=True):
  """Itera sobre los archivos de un zip.

  Args:
    - zip_obj: un objeto zipfile.ZipFile abierto en modo lectura
    - skip_toplevel: un booleano que indica si a los nombres de archivos se les
          debe quitar el nombre de directorio común (si lo hubiese)

  Yields:
    - tuplas (nombre_archivo, zipinfo_object).
  """
  zip_files = [pathlib.PurePath(f) for f in zip_obj.namelist()]
  all_parents = set()
  common_parent = pathlib.PurePath(".")

  if not zip_files:
    raise ErrorAlumno("archivo ZIP vacío")

  for path in zip_files:
    all_parents.update(path.parents)

  if strip_toplevel and len(zip_files) > 1:
    parents = {p.parts[0] for p in zip_files}
    if len(parents) == 1:
      common_parent = parents.pop()

  for fname in zip_files:
    if fname not in all_parents:
      yield (fname.relative_to(common_parent),
             zip_obj.getinfo(fname.as_posix()))


class Moss:
  """Guarda código fuente del alumno.
  """
  def __init__(self, pathobj, tp_id, padron):
    self._dest = pathobj / tp_id / id_cursada() / padron
    self._padron = padron
    self._dest.mkdir(parents=True, exist_ok=True)

  def save_data(self, filename, contents):
    """Guarda un archivo si es código fuente.

    Devuelve True si se guardó, False si se decidió no guardarlo.
    """
    path = self._dest / filename.name
    path.write_bytes(contents)
    return self._git(["add", path.name]) == 0

  def flush(self):
    """Termina de guardar los archivos en el repositorio.
    """
    self._git(["add", "--no-all", "."])
    self._git(["commit", "-m", "New upload {}".format(self._padron)])
    self._git(["push", "--force-with-lease", "origin", ":"])

  def _git(self, args):
    subprocess.call(["git"] + args, cwd=self._dest)


def zip_datetime(info):
  """Gets a datetime.datetime from a ZipInfo object.
  """
  return datetime.datetime(*info.date_time)


def send_reply(orig_msg, reply_text):
  """Envía una cadena de texto como respuesta a un correo recibido.
  """
  if not OAUTH_REFRESH_TOKEN:
    print("ENVIARÍA: {}".format(reply_text))
    return

  reply = email.message.Message(email.policy.default)
  reply.set_payload(reply_text, "utf-8")

  reply["From"] = GMAIL_ACCOUNT
  reply["To"] = orig_msg["From"]
  reply["Cc"] = orig_msg.get("Cc", "")
  reply["Subject"] = "Re: " + orig_msg["Subject"]
  reply["In-Reply-To"] = orig_msg["Message-ID"]

  # Poniendo en copia a la cuenta del corrector se consigue que sus respuestas
  # pasen de nuevo los filtros de Gmail y se reenvíen al ayudante apropiado.
  reply["Bcc"] = GMAIL_ACCOUNT

  creds = get_oauth_credentials()
  xoauth2_tok = "user=%s\1" "auth=Bearer %s\1\1" % (GMAIL_ACCOUNT,
                                                    creds.access_token)
  xoauth2_b64 = base64.b64encode(xoauth2_tok.encode("ascii")).decode("ascii")

  server = smtplib.SMTP("smtp.gmail.com", 587)
  server.ehlo()
  server.starttls()
  server.ehlo()  # Se necesita EHLO de nuevo tras STARTTLS.
  server.docmd("AUTH", "XOAUTH2 " + xoauth2_b64)
  server.send_message(reply)
  server.close()


def get_oauth_credentials():
  """Refresca y devuelve nuestras credenciales OAuth.
  """
  # N.B.: siempre re-generamos el token de acceso porque este script es
  # stateless y no guarda las credenciales en ningún sitio. Todo bien con eso
  # mientras no alcancemos el límite de refresh() de Google (pero no publican
  # cuál es).
  creds = oauth2client.client.OAuth2Credentials(
      "", CLIENT_ID, CLIENT_SECRET, OAUTH_REFRESH_TOKEN,
      datetime.datetime(2015, 1, 1),
      "https://accounts.google.com/o/oauth2/token", "corrector/1.0")

  creds.refresh(httplib2.Http())
  return creds

##

if __name__ == "__main__":
  sys.exit(main())

# vi:et:sw=2
