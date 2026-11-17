FROM ubuntu:24.04

RUN apt-get update && \
    apt-get install -y --no-install-recommends openssh-server sudo rsyslog && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir -p /var/run/sshd

# Lab-only account with a deliberately weak password, isolated network, no
# real secrets anywhere near this container.
RUN useradd -m -s /bin/bash labuser && \
    echo "labuser:LabPass123" | chpasswd && \
    echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config && \
    echo "PermitRootLogin no" >> /etc/ssh/sshd_config

# sshd logs via syslog (auth facility); rsyslog's default config already
# routes auth/authpriv to /var/log/auth.log, which both
# lab/tools/baseline-ssh-detector/detect.py and a Wazuh agent's
# localfile monitor can tail. (Previously sshd ran with -e, logging only
# to the container's stderr/docker logs -- fine for the log-based
# detector's own capture script, but invisible to anything that actually
# tails a file, including Wazuh.)
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 22
CMD ["/entrypoint.sh"]
