# ASUS regression tests

Build the real ARM64 payload with `asus/build.py` first. The test program
refuses to run outside its dedicated Docker fixture. It operates on a private
40 MiB `/jffs` tmpfs and a private network namespace; never pass host networking
or a host `/jffs` mount.

```sh
docker build -t tailscale-asus-test -f asus/tests/Dockerfile .
docker run --rm --network none --cap-add NET_ADMIN --device /dev/net/tun \
  --tmpfs /jffs:rw,exec,size=40m --tmpfs /tmp:rw,exec,size=512m \
  -e TS_ASUS_TEST_CONTAINER=1 -v "$PWD:/repo:ro" \
  tailscale-asus-test python3 asus/tests/test_manager.py
```

`testcontrol` is the qualified core's `cmd/testcontrol`, cross-built with
CGO disabled into `asus/out/testcontrol`. Build the startup-failure fixture:

```sh
CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build \
  -ldflags '-s -w -X main.core=a32d18362c987e5007eab9f76c69118947a7b047' \
  -o asus/out/stalled-daemon asus/tests/stalled-daemon.go
```

Set `TEST_SHELL=/usr/bin/dash` for the second shell round (Alpine's path).
Set `TS_ASUS_BASELINE_BUNDLE` to the 1.104.6 ARM64 gzip fixture for the actual
cross-core update/rollback case. This baseline is test data, never uploaded as
a 1.104.7 asset. Without it that single test is explicitly skipped.

Set `TS_ASUS_PREVIOUS_RELEASE_DIR` to a read-only fixture directory with the
published `v1.104.7` manager, ARM64 gzip and manifest to exercise the bootstrap
upgrade and rollback across the real release boundary.

Contracts covered: offline boot from persistent gzip, real TUN daemon startup,
identity preservation, two release slots, corrupt manifest/payload rejection,
flash exhaustion before stopping the active daemon, startup rollback, original
Merlin hook interpreter/exit/permissions/symlink restoration, hook ownership,
flock and PID ownership, Entware hook coexistence, cancellation during readiness,
power loss after activation, bounded RAM logging, crash supervision, private
control login and netfilter recovery, and rollback across different core commits.

The control test uses only container loopback plus a dummy interface without a
gateway. It makes no WAN DERP or production-network performance claim. These
tests do not replace physical router, mobile WAN, or every ASUS model acceptance.
