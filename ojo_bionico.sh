#!/bin/bash

set -eu

FIND="gfind"  # For macOS fiends.
which $FIND >/dev/null 2>&1 || FIND="find"

# TODO(dato): do not hardcode these.
MOSS="/srv/fiuba/75.41/corrector/bin/moss"
DATA="/srv/fiuba/75.41/corrector/data/tps"

TP="${1-}"
TP_DIR="$DATA/$TP"
MOSS_TITLE="TDA $TP/$(date +%Y-%m-%d)"

if [[ -z $TP ]]; then
  echo >&2 "Uso: $0 <NOMBRE_TP>"
  exit 1
fi

if [[ ! -d "$TP_DIR" ]]; then
  echo >&2 "No existe: $TP_DIR"
  exit 1
fi

TMP1=`mktemp`
TMP2=`mktemp`

trap "rm -f \"$TMP1\" \"$TMP2\"" EXIT

# xargs’ -n 1000000000 makes it fail if it would split the files into
# multiple moss invocations (which would defeate the point).
#
# `cd $TP_DIR` helps with the above by keeping the command line short.
#
CUR=$(ls "$TP_DIR" | sed -n '$p')
PAST=$(ls -r "$TP_DIR" | sed '1d')

for prev in $PAST; do
    ls "$TP_DIR/$prev" >"$TMP1"
    ls "$TP_DIR/$CUR"  >"$TMP2"
    EXCLUDE=$(comm -12 "$TMP1" "$TMP2" | sed "s#^#$prev/#" | tr '\n' '|')

    cd "$TP_DIR" && $FIND $CUR $prev -regextype egrep   \
        \( -name '0*' -o -regex "$EXCLUDE" \) -prune -o \
        -type f -name '*.c' -not -name '__MAC*' -print0 |
    xargs -0n 1000000000 $MOSS -d -l c -c "$MOSS_TITLE (vs $prev)"
done

# TODO(dato): capture URL and post to Slack.
