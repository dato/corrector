# -*- docker-image-name: "fiuba/corrector" -*-
# vi:et

FROM debian:8

RUN apt-get update && apt-get upgrade -y    && \
    apt-get install -y --no-install-recommends \
        build-essential valgrind time python3

COPY worker.py /

USER nobody
WORKDIR /tmp

ENTRYPOINT ["/worker.py"]
