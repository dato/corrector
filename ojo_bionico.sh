#!/bin/bash

set -eu

# TODO(dato): do not hardcode these.
MOSS="/srv/fiuba/75.41/corrector/bin/moss"
DATA="/srv/fiuba/75.41/corrector/data/tps"

TP="${1-}"
TP_DIR="$DATA/$TP"

if [[ -z $TP ]]; then
  echo >&2 "Uso: $0 <NOMBRE_TP>"
  exit 1
fi

if [[ ! -d "$TP_DIR" ]]; then
  echo >&2 "No existe: $TP_DIR"
  exit 1
fi

# xargs’ -n 1000000000 makes it fail if it would split the files into
# multiple moss invocations (which would defeate the point).
#
# `cd $TP_DIR` helps with the above by keeping the command line short.
#
cd "$TP_DIR" && find . -name '0*' -type d -prune -o \
     -type f -name '*.c' -not -name '__MAC*' -print0 |
  xargs -0n 1000000000 $MOSS -d -l c -c "TDA $TP ($(date +%Y-%m-%d))"

# TODO(dato): capture URL and post to Slack.
