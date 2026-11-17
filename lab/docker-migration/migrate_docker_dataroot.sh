#!/bin/bash
# Moves Docker's data-root from the near-full root disk (/) to the 1TB
# disk at /mnt/disk2. Requires sudo. Stops the Docker daemon briefly
# (containers with restart policy "always"/"unless-stopped" come back on
# their own; others need a manual `docker start` afterward).
set -euo pipefail

echo "== Stopping Docker =="
sudo systemctl stop docker docker.socket containerd

echo "== Creating new data-root on /mnt/disk2 =="
sudo mkdir -p /mnt/disk2/docker

echo "== Copying existing Docker data (this can take a few minutes) =="
sudo rsync -aP /var/lib/docker/ /mnt/disk2/docker/

echo "== Configuring Docker to use the new data-root =="
sudo mkdir -p /etc/docker
if [ -f /etc/docker/daemon.json ]; then
  sudo cp /etc/docker/daemon.json /etc/docker/daemon.json.bak
fi
sudo python3 -c "
import json, os
path = '/etc/docker/daemon.json'
cfg = {}
if os.path.exists(path):
    with open(path) as f:
        content = f.read().strip()
        if content:
            cfg = json.loads(content)
cfg['data-root'] = '/mnt/disk2/docker'
with open(path, 'w') as f:
    json.dump(cfg, f, indent=2)
print(open(path).read())
"

echo "== Starting Docker =="
sudo systemctl start docker

echo "== Done. Verify with: docker info --format '{{.DockerRootDir}}' =="
