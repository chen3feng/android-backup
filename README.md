# Android Backup

English | [简体中文](README-zh.md)

## Features

- Automatically pull files from your phone to a local backup directory
- Configurable list of directories to pull
- Incremental backup, only pulls new and changed files, typically completes in 3 minutes
- Supports multi-version backups, backing up a new snapshot to a new directory each time, and only increasing the storage space used by the changes
- Backs up multiple connected phones at once
- Supports wireless backup over the network

## Usage

### Installation

- Download and install [android-platform-tools](https://developer.android.com/tools/releases/platform-tools)
- Install [Python](https://www.python.org/), every programmer knows how to do it. 
- Install pathspec: `pip install pathspec`
- Enable USB debugging on your phone (https://developer.android.com/studio/debug/dev-options)
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

### Multi-version Backup

The default is single-version backup, which means that each backup refreshes the files in the backup directory, replacing any files that have changed.

Multi-version backup means that each backup creates a new backup directory named in the date format, such as `2025-08-03`. This leaves the previous backup directory, such as `2025-07-31`, unaffected. On file systems that support [hard links](https://en.wikipedia.org/wiki/Hard_link) (NTFS on Windows, the default file systems on Linux and Mac), this can significantly save hard disk storage space.
On file systems that don't support hard links, such as FAT32 and exFAT, multi-version backups are performed by copying, which is much slower. The storage space occupied by each version cannot be shared, so it's not advisable to retain too many historical versions.

Enable this feature in the device's configuration file:

```python
MULTIPLE_VERSIONS = True
```

### Wireless Network Backup

Enable wireless debugging on your phone and memorize the IP address and port, such as `172.20.9.21:35768`.

Run the `adb connect` command in the directory to connect to the phone:

```console
adb connect 172.20.9.21:35768
```

Other usage is the same as the USB method.

## Data Security

Although this isn't particularly relevant to this program, it's still worth mentioning. After all, I don't think anyone wants to be the next [Edison Chen](https://en.wikipedia.org/wiki/Edison_Chen_photo_scandal).

This program is primarily designed for portable storage devices, and portable hard drives are easily lost.

To prevent information leakage, it's strongly recommended to enable hard drive encryption, such as [BitLocker](https://learn.microsoft.com/en-us/windows/security/operating-system-security/data-protection/bitlocker/) on Windows, [External Hard Drive Encryption](https://support.apple.com/zh-cn/guide/disk-utility/dskutl35612/mac) on Mac, or the universal [VeraCrypt](hhttps://veracrypt.io/en/Downloads.html).

## Cross-Platform Backup

If you want to use your mobile storage device on both Windows and Mac, currently the only options are the [exFAT](https://learn.microsoft.com/en-us/windows/win32/fileio/exfat-specification) file system or the paid NTFS software on Mac.

When using exFAT, it is strongly recommended to store sensitive data using VeraCrypt.

## How It Works

Use the adb shell find command to scan the directory to be backed up on the phone, obtain a list of basic directory and file information, and compare it with the files in the local target directory:

- For directories that do not exist locally, use `adb pull <remote_directory> <local_directory>` to pull them.
- For files that already exist locally, compare the timestamps and file sizes. If they differ, use adb pull to pull them locally.
- For multi-version backups, first check whether the file with the same path already exists in the old backup, and check if the size and timestamp match. If so, create a hard link to the target backup directory.
