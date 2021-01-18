FROM ubuntu:focal

ADD packages.txt /tmp
ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update && grep '^[^ #]' /tmp/packages.txt        | \
        xargs apt-get install --yes --no-install-recommends && \
        rm -rf /var/lib/apt/lists/* /tmp/packages.txt

# TODO: cambiar a $INPUT_PATH antes de correr $INPUT_COMMAND.
ENTRYPOINT ["/bin/sh", "-c"]