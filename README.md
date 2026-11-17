# Tailscale AWG / QUIC

支持 OpenWrt、华硕原厂固件和 Asuswrt-Merlin，包含 AWG 与 QUIC 传输。

## OpenWrt 一键安装

```sh
curl -fsSL https://raw.githubusercontent.com/LiuTangLei/openwrt-tailscale-awg/main/install.sh | sh
```

## 华硕原厂 / 梅林一键安装

```sh
curl -fsSL https://gh-proxy.org/https://github.com/LiuTangLei/openwrt-tailscale-awg/releases/latest/download/install-asus.sh | /bin/sh
```

自动识别 ARM64 / ARMv7 和固件类型，压缩包保存在 JFFS，程序解压到内存运行。
梅林会自动启用 JFFS 自定义脚本；原厂需要已有的 fwtool custom-init 或 Entware 启动环境。
已在原厂 ET12 和 Gnuton 梅林 ET8 使用。[安装与管理说明](asus/README.md)

安装后进入中文管理菜单，可登录官方或自建控制服务器、配置 AWG/QUIC、查看状态和日志、更新或回滚。
重复执行同一命令即可打开菜单；同版本已安装时不会重复下载程序或重启服务。
下载内置 `gh-proxy.org`、`ghfast.top` 和 GitHub 直连切换，保留校验。
问题请提交 [Issue](https://github.com/LiuTangLei/openwrt-tailscale-awg/issues)。

OpenWrt 安装脚本基于 [GuNanOvO/openwrt-tailscale](https://github.com/GuNanOvO/openwrt-tailscale)。
