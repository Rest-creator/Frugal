#!/bin/bash
set -e

# rsyslogd runs as the unprivileged 'syslog' user, so a root-owned,
# root-only-writable auth.log (the default from a plain `touch` as root)
# makes rsyslog's omfile output silently suspend -- it can resolve the
# path but can't write to it. Match rsyslog's own expected ownership.
mkdir -p /var/log
touch /var/log/auth.log
chown syslog:adm /var/log/auth.log
chmod 640 /var/log/auth.log

rsyslogd
sleep 1

exec /usr/sbin/sshd -D
