[简体中文](README.md) | **English**  
![Tailscale & OpenWrt](./banner.png)  
# [Smaller Tailscale Repository For OpenWrt](https://gunanovo.github.io/openwrt-tailscale)

> [!NOTE]
> These are smaller Tailscale packages for OpenWrt, specifically designed to reduce storage usage while maintaining essential functionality.
> **Optimized:**
> - Combined `tailscale` and `tailscaled` into a single binary.
> - Built with the `--extra-small` flag to significantly reduce binary size.
> - UPX compression applied to binaries (except for mips64 architecture) to further reduce storage usage.

---

## Repository Setup

Add the package feed to your OpenWrt configuration:

**Edit `/etc/opkg/customfeeds.conf`:**

```sh
echo "src/gz openwrt-tailscale https://gunanovo.github.io/openwrt-tailscale" >> /etc/opkg/customfeeds.conf
````

**Or manually add this line:**

```sh
src/gz openwrt-tailscale https://gunanovo.github.io/openwrt-tailscale
```

---

## Installation Methods

Choose your preferred method to install Tailscale on OpenWrt:

### Web UI:

1. Navigate to **System → Software**
2. Click *Update lists* to refresh packages
3. Search for `tailscale`
4. Install the main package and any desired utilities

### Command Line:

```sh
opkg update
opkg install tailscale
```

> [!NOTE]
> The "failed log upload" message during installation is expected and can be safely ignored.

---

## Post-Installation Steps

After installation, you need to configure Tailscale to connect your device to the Tailscale network.

Run the following command:

```sh
tailscale up \
    --accept-dns=false \
    --advertise-routes=10.0.0.0/24 \
    --advertise-exit-node
```

---

> [!TIP]
> Consider adding `--hostname=your-router-name` for easier identification.

---

> 💖 If this project helps you, feel free to star⭐ it!  
