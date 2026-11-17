# mywealth-vm Docker data-root migration (2026-11-17)

`mywealth-vm`'s root disk (`/`, 49GB) filled to 96% during Wazuh's stand-up,
leaving no realistic room for OpenVAS's feed sync. A separate 1TB disk was
already attached at `/mnt/disk2` (910GB free at the time) but unused by
Docker.

`migrate_docker_dataroot.sh` moved Docker's entire data-root
(`/var/lib/docker` -> `/mnt/disk2/docker`) via `/etc/docker/daemon.json`.
This VM also runs an unrelated, pre-existing production stack
(`swaposell-*`, up 12 days at the time) sharing the same Docker daemon —
`*_before.txt` capture exactly what was running/present beforehand, so the
migration could be verified against a concrete baseline rather than "it
looks fine."

## What was verified after migration
- `docker info --format '{{.DockerRootDir}}'` -> `/mnt/disk2/docker`.
- Every container with a `restart: always`/`unless-stopped` policy
  (Wazuh's three + all four `swaposell-*`) came back up on its own.
- `frugal-victim` (no restart policy) needed a manual `docker start` +
  `wazuh-control start` for its agent daemons — expected, not a failure.
- The Wazuh agent's enrollment (`client.keys`) survived in the container's
  own writable layer; the manager still shows it `Active` post-migration.
- Both of `frugal-victim`'s network attachments (`frugal-lab_lab-net`,
  `single-node_default`) survived.
- Old `/var/lib/docker` removed only after all of the above was confirmed,
  freeing the root disk back down to 75% used (12GB free).

This directory is a point-in-time migration record, not a script meant to
run again — re-running it against an already-migrated host would rsync an
empty/wrong source.

**Note:** the `*_before.txt` files have had every `swaposell`/`swap-o-sell`
line removed before committing. That stack is a separate, unrelated
production service sharing this VM's Docker daemon — its container/port/
image topology isn't Frugal's to publish in a public repo. The migration
itself was still verified against it (see the report in the
SOFTWARE-ENGINEER repo's DevOps log), just not recorded here in detail.
