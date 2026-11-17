FROM ubuntu:24.04

RUN apt-get update && \
    apt-get install -y --no-install-recommends sshpass openssh-client && \
    rm -rf /var/lib/apt/lists/*

COPY attack.sh /attack.sh
RUN chmod +x /attack.sh

ENTRYPOINT ["/attack.sh"]
