# Android Backup

English | [简体中文](README-zh.md)

Automatically and incrementally back up files, photos, and more from your Android device (phone or tablet) to your computer's hard drive, USB flash drive, or external hard drive via a USB cable or wireless network.

Advantages:

- Saves money on cloud storage
- Fast, much faster than [MTP](https://en.wikipedia.org/wiki/Media_Transfer_Protocol#Performance)
- Only one setup required for new devices, with subsequent operations automatic
- No root required
- Open source and free

## Features

- Automatically pull files from your device to a local backup directory
- Configurable list of directories to pull
- Incremental backup, only pulls new and changed files, typically completes in 1 minutes if there are only a few changed files.
- Supports multi-version backups, backing up a new snapshot to a new directory each time, and only increasing the storage space used by the changes
- Backs up multiple connected devices at once
- Supports wireless backup over the network

## Usage

### Installation

- Download and install [android-platform-tools](https://developer.android.com/tools/releases/platform-tools)
  or use a package manager like home brew.
- Install [Python](https://www.python.org/), every programmer knows how to do it.
- Install pathspec: `pip install pathspec`
- Enable USB debugging on your device (https://developer.android.com/studio/debug/dev-options)
- Download the source code for this program.

### Configuration

This program is currently designed as a portable version and does not use the system configuration directory, making it easier to store on a portable hard drive or other storage device.

Global configuration `global.config`

```python
# Path to the adb command. Leave this blank for automatic search.
ADB_PATH=""

# The default root directory for the backup directory. Different devices are backed up to subdirectories within this directory.
BACKUP_BASE_DIR="backups"

# Which files and directories to exclude?
# This is already set, so generally don't need to be changed.
DEFAULT_EXCLUDE_FILE="exclude.txt"
```

Device configuration `devices/<serial>.conf`

In the `devices` subdirectory, serial is the actual device serial number.

```console
$ adb devices
List of devices attached
9527542b device
```

Here, `9527542b` is the device serial number, so the device configuration file path is `devices/9527542b.conf`

For specific configuration items, see the comments in [devices/example.conf](devices/example.conf).

### Backup

Windows:

```console
backup
```

Mac/Linux:

```console
./backup
```

A backup will automatically be performed after executing the command.

This is an example output:

```console
Find devices:
  serial=7654321 name="Xiaomi 12"
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

### Multi-version Backup

The default is single-version backup, which means that each backup refreshes the files in the backup directory, replacing any files that have changed.

Multi-version backup means that each backup creates a new backup directory named in the date format, such as `2025-08-03`. This leaves the previous backup directory, such as `2025-07-31`, unaffected. On file systems that support [hard links](https://en.wikipedia.org/wiki/Hard_link) (NTFS on Windows, the default file systems on Linux and Mac), this can significantly save hard disk storage space.

The backup directories for each date appear to be a full copy:

```console
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

But the actual increase in storage overhead is small:

```console
$ du -sh backups/xiaomi12/*
 31G    backups/xiaomi12/2025-08-01
2.9G    backups/xiaomi12/2025-08-02
 11M    backups/xiaomi12/2025-08-03
 98M    backups/xiaomi12/2025-08-04
 16M    backups/xiaomi12/2025-08-06
  0B    backups/xiaomi12/latest
```

On file systems that don't support hard links, such as FAT32 and exFAT, multi-version backups are performed by copying, which is much slower. The storage space occupied by each version cannot be shared, so it's not advisable to retain too many historical versions.

Enable this feature in the device's configuration file:

```python
MULTIPLE_VERSIONS = True
```

### Wireless Network Backup

Make sure your device and computer are connected to the same WiFi.
Enable [wireless debugging](https://developer.android.com/tools/adb?wireless-android11-command-line#connect-to-a-device-over-wi-fi) on your device,
you can see the IP address and port, such as `172.20.10.8:39915`.

Run the `adb connect` command to connect to the device:

```console
adb connect 172.20.9.21:35768
```

Other usage is the same as the USB method.

## Data Security

Although this isn't particularly relevant to this program, it's still worth mentioning. After all, I don't think anyone wants to be the next [Edison Chen](https://en.wikipedia.org/wiki/Edison_Chen_photo_scandal).

This program is primarily designed for portable storage devices, and theys are easily lost.

To prevent information leakage, it's strongly recommended to enable hard drive encryption, such as [BitLocker](https://learn.microsoft.com/en-us/windows/security/operating-system-security/data-protection/bitlocker/) on Windows, [External Hard Drive Encryption](https://support.apple.com/zh-cn/guide/disk-utility/dskutl35612/mac) on Mac, or the universal [VeraCrypt](hhttps://veracrypt.io/en/Downloads.html).

## Cross-Platform Backup

If you want to use your portable storage device on both Windows and Mac, currently the only options are the [exFAT](https://learn.microsoft.com/en-us/windows/win32/fileio/exfat-specification) file system or the paid NTFS software on Mac.

When using exFAT, it is strongly recommended to store sensitive data using VeraCrypt.

## Background

I've never paid for a cloud service. Partly because I find the monthly fees annoying, and partly because I don't trust these vendors. So, I've always manually backed up my phone's files to a local storage device using my computer.

I've tried a number of backup apps, some of which require rooting your phone, and some have limited free features.

I've also tried these manually ways:

- Copying files via the MTP protocol is a nightmare, it often results in disconnections and hangs.
- The FTP protocol is better but still not very fast enough.
- There are also apps that can display your phone like a portable hard drive.

Besides the stability issues, the main problem with all of these backup protocols and software is that they all require manual file selection for synchronization. Since there's no way to determine which files need to be updated, Is have to copy them all to the computer, which takes a long time each time.

After careful consideration, I realized I needed a tool like [rsync](https://download.samba.org/pub/rsync/rsync.1) that allows incremental transfers and customizable file filtering rules.

I did some research and found that transferring files via ADB is still the fastest, but ADB doesn't support incremental transfers. I found two similar tools, google/adb-sync, which is deprecated and better-adb-sync, which has very few features. Neither of them met my needs, so I developed this software.

## How It Works

This program is implemented in two layers:

The `adbsync` package implements the core synchronization functionality, providing synchronization functions similar to `rsync`. It can also be called directly from the command line using `python -m adbsync`:

```console
python -m adbsync /sdcard/./Documents backups/xiaomi9/
```

Run `python -m adbsync --help` for a complete description of the command line parameters.

The `backup` command provides a directory line user interface, responsible for identifying the currently connected device, loading the corresponding configuration file, checking the backup directory, and generating the appropriate parameters to call the `adbsync.pull` function.

The process of incremental pull:

- Use the `adb shell find` command to scan the directory to be backed up on the device, obtain a list of
  basic directory and file information, and compare it with the files in the local target directory.
- For directories that do not exist locally, use `adb pull <remote_directory> <local_directory>` to pull them directly.
- For existing files, compare the timestamps and file sizes. If they differ, use adb pull to pull them locally.
- For multi-version backups, first check whether the file with the same path already exists in the old backup,
  and see if the size and timestamp match. If so, hard link it to the target backup directory.
  If it doesn't match or doesn't exist, download it from the device.

## Related Projects

- [google/adb-sync](https://github.com/google/adb-sync) has been archived.
- [better-adb-sync](https://github.com/jb2170/better-adb-sync) has not been updated for two years.
