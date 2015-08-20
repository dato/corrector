#!/bin/bash
# vi:et:sw=2
#
# Script de instalación del corrector.

set -eu

if [[ `whoami` != "root" ]]; then
  echo >&2 "Must be run as root."
  exit 1
fi

source "conf/corrector.env"

##

# Instalar software

env DEBIAN_FRONTEND=noninteractive \
apt-get install --assume-yes --no-install-recommends \
    fetchmail python3 python3-oauth2client ca-certificates

##

# Crear usuarios

if ! getent group "$CORRECTOR_RUN_GROUP" >/dev/null; then
  addgroup --gid "$CORRECTOR_RUN_UID" "$CORRECTOR_RUN_GROUP"
fi

if ! getent passwd "$CORRECTOR_RUN_USER" >/dev/null; then
  adduser --system --shell /bin/false     \
     --uid "$CORRECTOR_RUN_UID"           \
     --gid "$CORRECTOR_RUN_UID"           \
     --disabled-password --disabled-login \
     --gecos "" "$CORRECTOR_RUN_USER"
fi

##

# Crear directorios

mkdir_p() {
  mkdir -p "${1}"
  chown "${2}" "${1}"
}

OWNER="$CORRECTOR_RUN_USER:$CORRECTOR_RUN_GROUP"

mkdir_p "$CORRECTOR_ROOT" "root:root"
mkdir_p "$CORRECTOR_ROOT/bin" "root:root"
mkdir_p "$CORRECTOR_ROOT/conf" "root:root"
mkdir_p "$CORRECTOR_ROOT/$CORRECTOR_TPS" "$OWNER"
mkdir_p "$CORRECTOR_ROOT/$CORRECTOR_SKEL" "root:root"

##

# Compilar el wrapper del worker.

gcc -o "$CORRECTOR_ROOT/$CORRECTOR_WORKER" \
    -std=c99 -Wall -pedantic -Werror worker/wrapper.c

chown root:docker "$CORRECTOR_ROOT/$CORRECTOR_WORKER"
chmod g+s "$CORRECTOR_ROOT/$CORRECTOR_WORKER"

##

# Copiar el script y los archivos de configuración.

install corrector.py "$CORRECTOR_ROOT/$CORRECTOR_MAIN"
install -m 400 conf/corrector.env "$CORRECTOR_ROOT/conf"
install -m 600 -o "$CORRECTOR_RUN_USER" -g "$CORRECTOR_RUN_GROUP" \
    conf/fetchmailrc "/home/$CORRECTOR_RUN_USER/.fetchmailrc"

cp conf/corrector.service /etc/systemd/system
systemctl daemon-reload

if [[ ! -e "/home/$CORRECTOR_RUN_USER/.netrc" ]]; then
  install -m 600 -o "$CORRECTOR_RUN_USER" -g "$CORRECTOR_RUN_GROUP" \
      conf/netrc.sample "/home/$CORRECTOR_RUN_USER/.netrc"
  echo >&2 "Actualizar /home/$CORRECTOR_RUN_USER/.netrc con la contraseña."
  exit 1
fi
