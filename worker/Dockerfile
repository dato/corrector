# -*- docker-image-name: "algoritmosrw/corrector" -*-

FROM ubuntu:xenial

RUN apt-get update     && \
    apt-get upgrade -y && \
    apt-get install -y gcc g++ clang libgtest-dev make valgrind time python3 &&  \
    make -f /usr/share/doc/libgtest-dev/examples/make/Makefile -C /usr/local/lib \
        gtest.a && ln -s gtest.a /usr/local/lib/libgtest.a

COPY worker.py /

USER nobody
WORKDIR /tmp

ENTRYPOINT ["/worker.py"]

# vi:et
