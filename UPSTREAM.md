# OpenWrt upstream integration

Based on GuNanOvO/openwrt-tailscale at
`436bb61937822c78a059cb7aa7e1c69280786da8` (2026-11-17 review).

Ported the Chinese and English installer fixes: detached installation,
verified staging, atomic replacement, cancellation and startup rollback,
configuration preservation, and persistent/RAM/binary mode management.
The tight-space OpenWrt installer uses a RAM backup; this does not survive
power loss. ASUS uses persistent compressed releases instead.

Also ported the flash-appliance build exclusion (aa624c2) and the optional
UPX check. Peer Relay and Taildrop remain enabled. Fork source, transport
pins, feed signing, build verification and release checks are unchanged.

The documentation site, optional buildroot helpers and development containers
are outside this integration. After this port, upstream 1.104.7 was merged
separately: Go 1.27.4 and the API proxy identity fix. The qualified core is
now v1.104.7 / a32d18362c987e5007eab9f76c69118947a7b047. Transport fork
pins remain unchanged. Application and dependency tags are both unsuffixed.
