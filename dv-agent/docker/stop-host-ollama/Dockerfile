FROM ubuntu:24.04
RUN apt-get update \
    && apt-get install -y --no-install-recommends util-linux \
    && rm -rf /var/lib/apt/lists/*
COPY stop.sh /stop.sh
RUN chmod +x /stop.sh
ENTRYPOINT ["/stop.sh"]
