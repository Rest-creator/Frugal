FROM ubuntu:24.04

RUN apt-get update && \
    apt-get install -y --no-install-recommends openssh-server sudo auditd && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir -p /var/run/sshd

# Lab-only account with a deliberately weak password, isolated network, no
# real secrets anywhere near this container.
RUN useradd -m -s /bin/bash labuser && \
    echo "labuser:LabPass123" | chpasswd && \
    echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config && \
    echo "PermitRootLogin no" >> /etc/ssh/sshd_config

EXPOSE 22
CMD ["/usr/sbin/sshd", "-D", "-e"]
