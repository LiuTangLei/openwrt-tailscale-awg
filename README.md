# Tailscale AWG / QUIC

支持 OpenWrt、华硕原厂固件和 Asuswrt-Merlin，包含 AWG 与 QUIC 传输。

## OpenWrt 一键安装

```sh
curl -fsSL https://raw.githubusercontent.com/LiuTangLei/openwrt-tailscale-awg/main/install.sh | sh
```

## 华硕原厂 / 梅林一键安装

```sh
curl -fsSL https://github.com/LiuTangLei/openwrt-tailscale-awg/releases/latest/download/install-asus.sh | sh
```

自动识别 ARM64 / ARMv7 和固件类型，压缩包保存在 JFFS，程序解压到内存运行。
梅林会自动启用 JFFS 自定义脚本；原厂需要已有的 fwtool custom-init 或 Entware 启动环境。
已在原厂 ET12 和 Gnuton 梅林 ET8 使用。[安装与管理说明](asus/README.md)

安装后自行登录网络；自建控制服务器和 AWG 参数沿用现有网络配置。
问题请提交 [Issue](https://github.com/LiuTangLei/openwrt-tailscale-awg/issues)。

OpenWrt 安装脚本基于 [GuNanOvO/openwrt-tailscale](https://github.com/GuNanOvO/openwrt-tailscale)。
