# Tailscale AWG / QUIC

支持 OpenWrt、华硕原厂固件和 Asuswrt-Merlin，包含 AWG 与 QUIC 传输。

## OpenWrt 一键安装

```sh
curl -fsSL https://raw.githubusercontent.com/LiuTangLei/openwrt-tailscale-awg/main/install.sh | sh
```

## 华硕原厂 / 梅林一键安装

```sh
curl -fsSL https://github.com/LiuTangLei/openwrt-tailscale-awg/releases/latest/download/install-asus.sh -o /tmp/install-asus.sh && /bin/sh /tmp/install-asus.sh
```

自动识别 ARM64 / ARMv7、内核版本与启动钩子，先预检再下载；压缩包保存在 JFFS，程序解压到内存运行。
请务必使用完整的 `/bin/sh`（华硕原厂固件的裸 `sh` 可能是硬件调试工具）。
梅林会自动启用 JFFS 自定义脚本；原厂需要已有的 fwtool custom-init 或 Entware 启动环境。
已在原厂 ET12 和 Gnuton 梅林 ET8 使用。[安装与管理说明](asus/README.md)

安装后进入中文管理菜单，可登录官方或自建控制服务器、配置 AWG/QUIC、查看状态和日志、更新或回滚。
安装完成后随时可离线执行 `/jffs/addons/tailscale-awg/tailscale-asus menu` 重新打开菜单；重复执行安装命令且同版本已安装时不会重复下载或重启服务。
安装脚本从 GitHub 下载。如果路由器无法直连，可以在电脑上下载脚本后传到路由器。
脚本支持 `--no-menu`，并为有固定校验值的文件提供镜像回退，可用 `--mirror https://<镜像>` 或 `TS_ASUS_MIRROR` 指定首选镜像。
问题请提交 [Issue](https://github.com/LiuTangLei/openwrt-tailscale-awg/issues)。

OpenWrt 安装脚本基于 [GuNanOvO/openwrt-tailscale](https://github.com/GuNanOvO/openwrt-tailscale)。
