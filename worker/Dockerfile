# -*- docker-image-name: "algoritmosrw/corrector" -*-

FROM ubuntu:xenial

RUN apt-get update     && \
    apt-get upgrade -y && \
    apt-get install -y gcc g++ clang make valgrind time python3

COPY worker.py /

USER nobody
WORKDIR /tmp

ENTRYPOINT ["/worker.py"]

# vi:et
