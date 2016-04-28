# -*- docker-image-name: "fiuba/corrector" -*-
# vi:et

FROM debian:8

RUN apt-get update && apt-get upgrade -y    && \
    apt-get install -y --no-install-recommends \
        build-essential valgrind libgtest-dev time python3  && \
    cd /tmp && \
    cp /usr/share/doc/libgtest-dev/examples/make/Makefile . && \
    make gtest.a gtest_main.a                               && \
    mv gtest.a /usr/local/lib/libgtest.a                    && \
    mv gtest_main.a /usr/local/lib/libgtest_main.a          && \
    rm -f Makefile *.a *.o

COPY worker.py /

USER nobody
WORKDIR /tmp

ENTRYPOINT ["/worker.py"]
