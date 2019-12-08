# -*- docker-image-name: "algoritmosrw/corrector" -*-

FROM ubuntu:bionic

RUN apt-get update     && \
    apt-get upgrade -y && \
    apt-get install -y gcc gcc-multilib g++ clang      \
                       make valgrind time python3 perl \
                       openjdk-11-jdk-headless         \
                       libgtest-dev python3-jinja2 &&  \
    make -f /usr/src/googletest/googletest/make/Makefile -C /usr/local/lib \
        gtest.a && ln -s gtest.a /usr/local/lib/libgtest.a

COPY ["*.py", "*.j2", "/"]

USER nobody
WORKDIR /tmp

ENTRYPOINT ["/worker.py"]

# vi:et
