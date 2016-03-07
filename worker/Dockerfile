# -*- docker-image-name: "fiuba/corrector" -*-
# vi:et

FROM debian:8

RUN apt-get update && env DEBIAN_FRONTEND=noninteractive \
    apt-get install --assume-yes --no-install-recommends \
        build-essential valgrind time python3

COPY worker.py /

USER nobody
WORKDIR /tmp

ENTRYPOINT ["/worker.py"]
