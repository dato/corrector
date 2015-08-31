#!/usr/bin/env python3

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
"""

# TODO(dato): guardar las entregas en un directorio para pasarles Moss.

import base64
import datetime
import email
import email.message
import email.policy
import email.utils
import io
import mimetypes
import os
import re
import smtplib
import subprocess
import sys
import tarfile
import zipfile

import httplib2
import oauth2client.client

ROOT_DIR = os.environ["CORRECTOR_ROOT"]
SKEL_DIR = os.path.join(ROOT_DIR, os.environ["CORRECTOR_SKEL"])
WORKER_BIN = os.path.join(ROOT_DIR, os.environ["CORRECTOR_WORKER"])

MAX_ZIP_SIZE = 1024 * 1024  # 1 MiB

# Si estas variables no están definidas, el mail no se envía sino que se imprime
# por pantalla.
GMAIL_ACCOUNT = os.environ.get("CORRECTOR_ACCOUNT")
CLIENT_ID = os.environ.get("CORRECTOR_OAUTH_CLIENT")
CLIENT_SECRET = os.environ.get("CORRECTOR_OAUTH_SECRET")
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
    sys.stderr.write("Ignorando email de {}".format(GMAIL_ACCOUNT))
    return

  tp_id = guess_tp(msg['Subject'])
  zip_obj = find_zip(msg)

  # Lanzar ya el proceso worker para poder pasar su stdin a tarfile.open().
  worker = subprocess.Popen([WORKER_BIN],
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)

  skel_dir = os.path.join(SKEL_DIR, tp_id)
  skel_files = set()

  tar = tarfile.open(fileobj=worker.stdin, mode="w|")

  # Añadir al archivo TAR la base del TP (skel_dir).
  for path, _, filenames in os.walk(skel_dir):
    for fname in filenames:
      full_path = os.path.join(path, fname)
      arch_path = os.path.relpath(full_path, skel_dir)
      skel_files.add(arch_path)
      tar.add(full_path, arch_path)

  # A continuación añadir los archivos de la entrega (ZIP).
  add_from_zip(tar, zip_obj, skiplist=skel_files)
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
  candidates = {x.lower(): x for x in os.listdir(SKEL_DIR)}
  subj_words = [x.lower() for x in re.split(r"[^_\w]+", subject)]

  for word in subj_words:
    if word in candidates:
      return candidates[word]

  raise ErrorAlumno("no se encontró nombre del TP en el asunto")


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

    if extension and extension.lower() == '.zip':
      zipbytes = part.get_payload(decode=True)
      if len(zipbytes) > MAX_ZIP_SIZE:
        raise ErrorAlumno(
            "archivo ZIP demasiado grande ({} bytes)".format(len(zipbytes)))
      return zipfile.ZipFile(io.BytesIO(zipbytes))

  raise ErrorAlumno("no se encontró un archivo ZIP en el mensaje")


def add_from_zip(tar_obj, zip_obj, skiplist=()):
  """Reliza la unión de los archivos base de un TP con la entrega.

  Args:
    - tar: un objeto tarfile.TarFile abierto en modo escritura
    - zip_obj: un objeto zipfile.ZipFile abierto en modo lectura
    - skiplist: archivos a ignorar si están presentes en el ZIP
  """
  # Comprobar primero si los contenidos del ZIP están todos en un mismo
  # directorio.
  zip_files = zip_obj.namelist()
  strip_len = 0

  if not zip_files:
    raise ErrorAlumno("archivo ZIP vacío")

  # Ignorar el directorio si solo hay uno de primer nivel.
  dirname = os.path.dirname(zip_files[0])

  if dirname and all(x.startswith(dirname + "/") for x in zip_files):
    strip_len = len(dirname) + 1

  for fname in zip_files:
    arch_name = os.path.normpath(fname[strip_len:])
    # TODO(dato): mover el cleanup de *.o al Makefile.
    if fname.endswith(".o") or arch_name in skiplist:
      continue
    if arch_name.startswith("/") or ".." in arch_name:
      raise ErrorAlumno("ruta no aceptada: {} ({})".format(fname, arch_name))
    zinfo = zip_obj.getinfo(fname)
    tinfo = tarfile.TarInfo(arch_name)
    tinfo.size = zinfo.file_size
    if fname.endswith("/"):
      tinfo.type, tinfo.mode = tarfile.DIRTYPE, 0o755
    else:
      tinfo.type, tinfo.mode = tarfile.REGTYPE, 0o644
    tar_obj.addfile(tinfo, zip_obj.open(fname))


def send_reply(orig_msg, reply_text):
  """Envía una cadena de texto como respuesta a un correo recibido.
  """
  if not GMAIL_ACCOUNT:
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
  server.docmd('AUTH', 'XOAUTH2 ' + xoauth2_b64)
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
