# 安卓自动备份系统

[English](README.md) | 简体中文

通过 USB 电缆或者无线网络，把您的安卓设备（手机或者平板电脑）上的文件、照片等一键自动增量备份到电脑上的硬盘、U 盘或者移动硬盘中。

优点：

- 节省买云存储的钱
- 速度很快，比 [MTP](https://www.chiphell.com/thread-2580499-1-1.html) 方式快多了
- 新设备只需要一次设置，后续自动操作
- 设备无需 root
- 开源且免费

## 功能

- 自动拉取设备上的文件到本地备份目录下
- 待拉取的目录的列表可配置
- 增量备份，只拉取新增和变化的文件，文件变化很少时不到一分钟就能完成
- 支持多版本备份，每次备份一个新的快照到一个新的目录，在并且使用的存储空间只增加变化的部分
- 一次备份多个连接设备
- 支持通过网络无线备份

## 用法

### 安装

- 安装 [android-platform-tools](https://developer.android.com/tools/releases/platform-tools?hl=zh-cn)，下载安装或者通过包管理工具比如 home brew 来安装都可以。
- 安装 [Python](https://www.python.org/)，程序员都会。
- 安装 pathspec：`pip install pathspec`
- 设备开启 [USB 调试](https://developer.android.com/studio/debug/dev-options?hl=zh-cn)
- 下载本程序的源代码。

### 配置

本程序目前设计为绿色版，不使用系统的配置目录，方便放在移动硬盘等存储设备上。

全局配置 `global.config`

```python
# adb 命令的路径，留空自动查找
ADB_PATH=""

# 默认备份目录的根目录，不同设备备份到该目录下子目录中
BACKUP_BASE_DIR="backups"

# 那些文件和目录排除掉，已经设置好，一般不用管
DEFAULT_EXCLUDE_FILE="exclude.txt"
```

设备配置 `devices/<serial>.conf`

在 `devices` 子目录下，serial 为实际的设备序列号。

```console
$ adb devices
List of devices attached
9527542b        device
```

此处的 `9527542b` 即位设备序列号，那么设备的配置文件路径为 `devices/9527542b.conf`

具体配置项参见 [devices/example.conf](devices/example.conf) 中的注释。

### 备份

Windows 系统：

```
backup
```

Mac/Linux 系统：

```
./backup
```

执行命令后即会自动执行备份。

输出示例：

```console
Using adb path: /usr/local/bin/adb
Find devices:
  serial=7654321 name="Xiaomi 12"
Loaded device configuration: Xiaomi 12
Backup device Xiaomi 12 to backups/xiaomi12
Pulling /sdcard/DCIM...
/sdcard/DCIM/Camera/IMG_20250803_145317.jpg: 1 file pulled, 0 skipped. 26.3 MB/s (842953 bytes in 0.031s)
/sdcard/DCIM/Camera/IMG_20250803_141647.jpg: 1 file pulled, 0 skipped. 30.4 MB/s (937803 bytes in 0.029s)
/sdcard/DCIM/Camera/IMG_20250803_144114.jpg: 1 file pulled, 0 skipped. 34.0 MB/s (3944176 bytes in 0.111s)
/sdcard/DCIM/Camera/IMG_20250803_144732.jpg: 1 file pulled, 0 skipped. 30.1 MB/s (992072 bytes in 0.031s)
/sdcard/DCIM/Camera/IMG_20250803_145240.jpg: 1 file pulled, 0 skipped. 28.5 MB/s (798837 bytes in 0.027s)
/sdcard/DCIM/Camera/IMG_20250803_145619.jpg: 1 file pulled, 0 skipped. 26.9 MB/s (653076 bytes in 0.023s)
/sdcard/DCIM/Camera/IMG_20250803_145051.jpg: 1 file pulled, 0 skipped. 25.4 MB/s (544515 bytes in 0.020s)
/sdcard/DCIM/Camera/IMG_20250803_144829.jpg: 1 file pulled, 0 skipped. 28.2 MB/s (673078 bytes in 0.023s)
Pulling /sdcard/Documents...
Pulling /sdcard/Download...
Pulling /sdcard/Movies...
Pulling /sdcard/Music...
Pulling /sdcard/Pictures...
Updated latest link to 2025-08-03
```

### 多版本备份

默认是单版本备份，也就是说每次备份时刷新备份目录中的文件，替换掉有变化的文件。

多版本备份是指每次备份时产生一个全新的备份目录，以日期格式命名，比如 `2025-08-03`，这样先前的备份目录比如 `2025-07-31` 不受影响。在支持[硬链接](https://sspai.com/post/66834)的文件系统上（Windows 上的 NTFS，Linux 和 Mac 的默认文件系统都支持），可以大幅度节省硬盘存储空间开销。

```console
$ du -sh backups/xiaomi12/*
 31G    backups/xiaomi12/2025-08-01
2.9G    backups/xiaomi12/2025-08-02
 11M    backups/xiaomi12/2025-08-03
 98M    backups/xiaomi12/2025-08-04
 16M    backups/xiaomi12/2025-08-06
  0B    backups/xiaomi12/latest

$ du -sh backups/xiaomi12/2025-08-01/
 31G    backups/xiaomi12/2025-08-01/
$ du -sh backups/xiaomi12/2025-08-02/
 34G    backups/xiaomi12/2025-08-02/
$ du -sh backups/xiaomi12/2025-08-03/
 31G    backups/xiaomi12/2025-08-03/
$ du -sh backups/xiaomi12/2025-08-04/
 31G    backups/xiaomi12/2025-08-04/
$ du -sh backups/xiaomi12/2025-08-06/
 31G    backups/xiaomi12/2025-08-06/
```

在不支持硬链接的文件系统上，比如 FAT32 和 exFAT，多版本备份是以拷贝的方式进行的，因此速度慢很多，每个版本存储空间占用也无法共享，因此不宜保留太多的历史版本。

在设备的配置文件中通过配置开启：

```python
MULTIPLE_VERSIONS = True
```

### 无线网络备份

首先确保设备和电脑都接入同一个 WiFi，然后在设备上打开[无线调试](https://developer.android.com/tools/adb?hl=zh-cn#connect-to-a-device-over-wi-fi)功能，你就能看到一个 IP 地址和端口，比如 `172.20.10.8:39915`。

运行 `adb connect` 命令即可连接到设备：

```console
adb connect 172.20.10.8:39915
```

其余用法同 USB 方式。

## 数据安全

虽然这个话题和本程序没有直接关系，但是还是值得提醒一下，毕竟我想没人想成为第二个[冠希哥](https://zh.wikipedia.org/wiki/%E9%99%B3%E5%86%A0%E5%B8%8C%E8%A3%B8%E7%85%A7%E4%BA%8B%E4%BB%B6)。

本程序主要为移动存储设备设计，而移动硬盘很容易丢失。

为了防止信息泄漏，强烈建议开启硬盘加密方式，比如 Windows 上的 [BitLocker](https://learn.microsoft.com/zh-cn/windows/security/operating-system-security/data-protection/bitlocker/)，Mac 上的[外置硬盘加密](https://support.apple.com/zh-cn/guide/disk-utility/dskutl35612/mac)，或者通用的 [VeraCrypt](https://juejin.cn/post/6844903774901764103)。

## 跨平台备份

如果移动存储设备要同时在 Windows 和 Mac 上使用，目前看只能选择 [exFAT](https://learn.microsoft.com/zh-cn/windows/win32/fileio/exfat-specification) 文件系统，或者 Mac 上 的 NTFS 收费软件。

使用 exFAT 时，强烈建议敏感数据用 VeraCrypt 来存储。

## 背景

我一直没有花钱购买云服务，一方面是觉得每个月都要付费很烦，另一方面我也不是很信任这些厂商，所以我过去都是通过电脑把手机上的文件手动备份到本地存储设备上。

我尝试过不少备份软件，有的需要 root 手机，有的免费版功能很少。

手工的方式则尝试过：

- 通过 MTP 协议复制文件简直是一场噩梦，经常掉线卡死。
- FTP 协议 比 MTP 稳定多了，但是也不是很快。
- 还有一些软件可以把手机像类似移动硬盘一样的显示。

通过所有以上这些协议和软件备份，除了稳定性问题以外，主要的麻烦是都需要手工选择文件同步。由于无法判断哪些文件需要更新，只好一股脑地复制到电脑，每次都耗时很久。

仔细考量后，我发现我需要的是一个像 [rsync](https://www.ruanyifeng.com/blog/2020/08/rsync.html) 一样能增量传输，自定义传输文件过滤规则的工具。

我调查了一下，发现目前通过 adb 方式传输文件依然是最快的，但是 adb 不支持增量传输。找到两个类似的工具，其中 google/adb-sync 已经废弃，better-adb-sync 功能也很少。这些都无法满足我的要求，因此我开发了这个软件。

## 工作原理

本程序分两层来实现：

`adbsync` 包实现了同步的核心功能，提供了类似 `rsync` 的同步函数，也可以通过 `python -m adbsync` 以命令行方式直接调用：

```console
python -m adbsync /sdcard/./Documents backups/xiaomi9/
```

运行 `python -m adbsync --help` 可以看到完整的命令行参数说明。

`backup` 命令则提供了目录行用户界面，负责识别当前连接的设备，加载相应的配置文件，检查备份目录，生成相应的参数调用 `adbsync.pull` 函数。

增量拉取的工作原理：

- 使用 adb shell find 命令扫描设备上的待备份的目录，得到目录和文件基本信息列表，和本地目标目录中的文件比较。
- 本地不存在的目录，直接用 `adb pull 远程目录 本地目录` 的方式拉取。
- 本地已有的文件，比较时间戳和文件大小，如果不同就用 adb pull 拉取到本地。
- 在多版本备份方式下，先查找旧的备份中是否已存在同路径的文件，大小和时间戳是否一致，如果一致就用硬链接的方式链接到目标备份目录下，不一致或者不存在的在从设备下载。

## 相关项目

- [google/adb-sync](https://github.com/google/adb-sync) 已废弃。
- [better-adb-sync](https://github.com/jb2170/better-adb-sync) 已两年没更新。
