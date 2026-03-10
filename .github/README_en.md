[简体中文文档](./README.md) | **English Docs**

![Tailscale & OpenWrt](./banner.png)

# The Latest, Smaller Tailscale-AWG for OpenWrt Devices

![GitHub release](https://img.shields.io/github/v/release/LiuTangLei/openwrt-tailscale-awg?style=flat-square&color=2196f3)
![Views](https://api.visitorbadge.io/api/combined?path=https%3A%2F%2Fgithub.com%2FLiuTangLei%2Fopenwrt-tailscale-awg&label=Views&countColor=%23a8d08d&style=flat-square)
![Downloads](https://img.shields.io/github/downloads/LiuTangLei/openwrt-tailscale-awg/total?style=flat-square&color=4caf50)
![GitHub Stars](https://img.shields.io/github/stars/LiuTangLei/openwrt-tailscale-awg?label=Stars&color=f1c40f&style=flat-square)
![OpenWrt 24.10](https://img.shields.io/badge/OpenWrt-24.10-2196f3?style=flat-square&logo=OpenWrt&logoColor=white&labelColor=1565c0)
![OpenWrt 25.12](https://img.shields.io/badge/OpenWrt-25.12-2196f3?style=flat-square&logo=OpenWrt&logoColor=white&labelColor=1565c0)
![IPK Package](https://img.shields.io/badge/IPK%20Package-OpenWrt-42a5f5?style=flat-square&logo=OpenWrt&logoColor=white&labelColor=1976d2)
![APK Package](https://img.shields.io/badge/APK%20Package-OpenWrt-42a5f5?style=flat-square&logo=OpenWrt&logoColor=white&labelColor=1976d2)

### This repository provides:

* The latest and smaller **Tailscale-AWG ipk packages** and **Tailscale-AWG apk packages** for multiple architectures
* One-click installation scripts supporting **persistent installation** and **temporary installation** on your OpenWrt 24.10 or OpenWrt 25.12 device
* An **OPKG and APK feed** for easier and continuous updates ➡️ [ [Smaller Tailscale-AWG Repo](https://liutanglei.github.io/openwrt-tailscale-awg/) ]

---

### Usage:

> [!WARNING]
> Please read the following before use
> **Requirements:**
>
> * **Storage**: Less than 8MB (except `mips64`, `riscv64`, `loongarch64`)
> * **RAM**: About 60MB (runtime)
> * **Network**: Ability to access GitHub
>
> **Notes:**
>
> * Devices with less than 256MB RAM may fail to run Tailscale; see [About memory usage](https://github.com/LiuTangLei/openwrt-tailscale-awg/issues/17)
> * Temporary installation heavily depends on network stability and is less reliable — recommended only for devices where persistent installation is impossible
> * Most devices/architectures are untested; if you encounter issues, please open an issue and I will respond as soon as possible

#### One-click CLI Installation Script

SSH into your OpenWrt device and run:

```bash
wget -O /usr/sbin/install.sh https://raw.githubusercontent.com/LiuTangLei/openwrt-tailscale-awg/main/install_en.sh && chmod +x /usr/sbin/install.sh && /usr/sbin/install.sh
```

#### Add OPKG/APK Feed

See the [feed branch README](https://github.com/LiuTangLei/openwrt-tailscale-awg/tree/feed) or the repository page: [Smaller Tailscale-AWG Repository For OpenWrt](https://liutanglei.github.io/openwrt-tailscale-awg/)

Only ipk and apk packages for supported architectures are included.

#### Manual ipk/apk Installation

1. Download the ipk or apk package matching your device architecture from [Releases](https://github.com/LiuTangLei/openwrt-tailscale-awg/releases)
2. On your OpenWrt device's web UI, go to System → Software → Upload Package, select the downloaded package, and install it

> [!NOTE]
> The ultimate criterion for a successful installation is whether `tailscale up` runs correctly. If it returns a login URL, the installation succeeded. If it shows `command not found` or other errors, the installation failed.

#### Recommended LuCI GUI

For easier usage with minimal CLI interaction, you may optionally use the community LuCI app from @Tokisaki-Galaxy's open-source project: [luci-app-tailscale-community](https://github.com/Tokisaki-Galaxy/luci-app-tailscale-community)

### Additional Notes:

> [!NOTE]
> If you experience any of the following:
>
> 1. Very high memory usage by Tailscale
> 2. Tailscale being killed and restarted by OOM Killer
> 3. Unexpected Tailscale restarts with unknown cause
>
> You can trade higher CPU usage for lower memory usage as follows:
>
> 1. Edit `/etc/init.d/tailscale`
>
>    ```bash
>    vi /etc/init.d/tailscale
>    ```
> 2. Locate the line:
>
>    ```bash
>    procd_set_param env TS_DEBUG_FIREWALL_MODE="$fw_mode"
>    ```
> 3. Append `GOGC=10` to the line:
>
>    ```bash
>    procd_set_param env TS_DEBUG_FIREWALL_MODE="$fw_mode" GOGC=10
>    ```
>
> This makes Tailscale reclaim memory more aggressively.
> For more details, see issue: [About memory usage](https://github.com/LiuTangLei/openwrt-tailscale-awg/issues/17)

---

### Build Optimizations

The following build options are used to minimize Tailscale.
See [Makefile](../package/tailscale/Makefile) for details:

* **[TAGS](../package/tailscale/Makefile#L31)**:

```
ts_include_cli,ts_omit_aws,ts_omit_bird,ts_omit_completion,ts_omit_kube,ts_omit_systray,ts_omit_taildrop,ts_omit_tap,ts_omit_tpm,ts_omit_relayserver,ts_omit_capture,ts_omit_syspolicy,ts_omit_debugeventbus,ts_omit_webclient
```

* **[LDFLAGS](../package/tailscale/Makefile#L29)**:

```
-s -w
```

Binary compression is performed using [UPX](https://upx.github.io/) with:

```
--best --lzma
```

---

### Script Logic

* **Persistent installation**: Automatically downloads ipk/apk packages and installs them using `opkg install` or `apk add`
* **Temporary installation**: Downloads the binary executable to `/tmp` and creates a script symlink in `/usr/sbin`

For details, see [install_en.sh](../install_en.sh)

---

### Powered By

**[[UPX](https://upx.github.io/)]** – Binary compression technology that makes ultra‑small Tailscale builds possible  
**[[GitHub Actions](https://github.com/features/actions)]** – Used for automated build, release, and feed deployment  

---

### Issue Reporting

Please submit issues via [Issues](https://github.com/LiuTangLei/openwrt-tailscale-awg/issues) and include:

1. Target platform architecture (`opkg print-architecture`)
2. Installation mode (persistent / temporary / opkg / apk)
3. Relevant log snippets

---

### Forking This Project

If you plan to fork this project, please check [Notes on Forking](./FORK.md) .

---

### Security Statement

This project is a third‑party compressed and optimized redistribution based on [LiuTangLei/tailscale](https://github.com/LiuTangLei/tailscale) (which itself is based on the official Tailscale source code and adds Amnezia WireGuard support). It is unrelated to the official project. All source code, scripts, and packages are provided “AS IS”. All build, packaging, and release steps are automated by [GitHub Actions](https://github.com/LiuTangLei/openwrt-tailscale-awg/actions). By using this project, you acknowledge and assume all potential security and stability risks.

---

### License

This project is licensed under the **MIT License** and includes code from [**LiuTangLei/tailscale**](https://github.com/LiuTangLei/tailscale) and [**Tailscale**](https://github.com/tailscale/tailscale); the relevant parts are licensed under **BSD 3-Clause**.

---

> 💖 If this project helps you, please consider giving it a ⭐!