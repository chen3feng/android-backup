"""
Backup files from device to local storage incrementally.
"""

import collections
import os
import posixpath
import re
import subprocess
import sys
import types
import typing

from datetime import datetime
from importlib.machinery import SourceFileLoader

import adbsync


Device = collections.namedtuple('Device', ['address', 'serial', 'name'])


def main() -> int:  # pylint: disable=missing-function-docstring
    config = load_config('global', os.path.join(os.path.dirname(__file__), 'global.conf'))
    if not config:
        print("No global configuration found.")
        return 1
    adb_path = config.ADB_PATH
    if not adb_path:
        adb_path = find_adb_path()
    if not adb_path:
        print("ADB_PATH not found in configuration or environment.")
        return 1

    devices = find_devices(adb_path)
    if not devices:
        print("No device connected.")
        return 1

    print("Find devices:")
    for device in devices:
        if device.address == device.serial:
            print(f'  serial={device.serial} name="{device.name}"')
        else:
            print(f'  serial={device.serial} name="{device.name}" address={device.address}')

    device_configs = load_device_configs(devices)
    if not device_configs:
        return 1

    ret = 0
    for device in devices:
        if pull_device(adb_path, device, config, device_configs[device.serial]) != 0:
            ret = 1
    return ret


def load_device_configs(devices: typing.List[Device]) -> typing.Dict[str, types.ModuleType]:
    """Load configurations for all found devices."""
    device_configs = {}
    for device in devices:
        config_path = os.path.join(os.path.dirname(__file__), 'devices', f'{device.serial}.conf')
        if not os.path.exists(config_path):
            print(f"No configuration {config_path} found.")
            return {}
        config = load_config(device.serial, config_path)
        if not config:
            print(f"Failed to load device configuration from {config_path}.")
            return {}
        device_configs[device.serial] = config
    return device_configs


def pull_device(adb_path, device, config, device_config):
    """Pull files from device to local according to its config."""
    device_backup_dir = posixpath.join(config.BACKUP_BASE_DIR, device_config.BACKUP_DIR)
    device_backup_dir = posixpath.normpath(device_backup_dir)
    print(f'Backup device {device.name} to {device_backup_dir}')
    multiple_versions = getattr(device_config, 'MULTIPLE_VERSIONS', False)
    if multiple_versions:
        # Use daily backup to avoid too many backups.
        version_dir = datetime.now().strftime("%Y-%m-%d")
        backup_dir = posixpath.join(device_backup_dir, version_dir)
        os.makedirs(backup_dir, exist_ok=True)
        latest_file, old_backup_dir = get_last_backup_dir(device_backup_dir)
    else:
        backup_dir = device_backup_dir
        old_backup_dir = None

    adbsync.pull(
        adb_path=adb_path,
        address=device.address,
        source_dirs=device_config.INCLUDE_DIRS,
        target_dir=backup_dir,
        old_backup_dir=old_backup_dir,
        exclude_file=config.DEFAULT_EXCLUDE_FILE,
    )

    if multiple_versions:
        if update_latest(latest_file, version_dir):
            print(f"Updated latest -> {version_dir}")
        else:
            print(f"Failed to update latest link to {version_dir}")
            if sys.platform.startswith("win"):
                print("提示：Windows 上创建符号链接需要管理员权限或开启开发者模式")

    return 0


def get_last_backup_dir(device_backup_dir) -> typing.Tuple[str, typing.Optional[str]]:
    """
    Get the last backup directory from the latest symlink or tag file.
    If the symlink or tag file does not exist, return None.
    """
    latest_file = posixpath.join(device_backup_dir, 'latest')
    if os.path.exists(latest_file):
        if os.path.islink(latest_file):
            old_backup_dir = os.readlink(latest_file)
            if not os.path.isabs(old_backup_dir):
                old_backup_dir = posixpath.join(device_backup_dir, old_backup_dir)
            return latest_file, old_backup_dir
        with open(latest_file, 'r', encoding='utf-8') as f:
            old_backup_dir = f.read().strip()
        if not os.path.isabs(old_backup_dir):
            old_backup_dir = posixpath.join(device_backup_dir, old_backup_dir)
        return latest_file, old_backup_dir
    return latest_file, None


def update_latest(latest_file, version_dir) -> bool:
    """
    Update the latest symlink or tag file to point to the new version directory.
    """
    if os.path.exists(latest_file):
        if os.path.islink(latest_file):
            return update_symlink(latest_file, version_dir)
        else:
            return update_tag_file(latest_file, version_dir)
    else:
        if not update_symlink(latest_file, version_dir):
            return update_tag_file(latest_file, version_dir)
    return False


def update_symlink(latest_file, version_dir) -> bool:
    """Update the target path of a symlink."""
    if os.path.exists(latest_file) and os.path.islink(latest_file):
        if os.readlink(latest_file) == version_dir:
            return True
        os.remove(latest_file)
    try:
        os.symlink(version_dir, latest_file, target_is_directory=False)
        return True
    except OSError:
        pass
    return False


def update_tag_file(latest_file, version_dir) -> bool:
    """Update the target path in a tag file."""
    try:
        with open(latest_file, 'w', encoding='utf-8') as f:
            f.write(version_dir)
            return True
    except OSError as e:
        print(f"[ERROR] Failed to create link file: {e}")
    return False


def load_config(name, config_file)-> typing.Optional[types.ModuleType]:
    """
    Load global configuration from a file.
    The name should be unique; otherwise, it returns the existing one.
    """
    try:
        # pylint: disable=deprecated-method
        config = SourceFileLoader(name, config_file).load_module(name)
        return config
    except Exception as e: # pylint: disable=broad-exception-caught
        print(f"Error loading configuration from {config_file}: {e}")
        return None


def find_adb_path() -> str:
    """
    Find the adb executable path.
    This function should be implemented to locate the adb executable.
    """
    which = 'which'
    suffix = ''
    if os.name == 'nt':
        which = 'where'
        suffix = '.exe'
    result = subprocess.run([which, 'adb'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL,
                            text=True, check=False)
    if result.returncode == 0:
        adb_path = result.stdout.strip()
        return adb_path
    if os.environ.get('ANDROID_HOME'):
        adb_path = os.path.join(os.environ['ANDROID_HOME'], 'platform-tools', 'adb' + suffix)
        if os.path.exists(adb_path):
            return adb_path

    return ''


def find_devices(adb: str) -> typing.List[Device]:
    """
    Find the device_id and serial number.
    When ABD is connected wireless, the device_id is IP:Port, otherwise it is serial
    """
    result = []
    try:
        output = subprocess.check_output([adb, 'devices'], text=True)
        for line in output.splitlines():
            if '\tdevice' in line:
                address = line.split('\t')[0]
                serial = get_device_serial(adb, address)
                name = get_device_name(adb, address)
                result.append(Device(address, serial, name))
    except subprocess.CalledProcessError as e:
        print(f"Error finding device information: {e}")
    return result


def get_device_serial(adb, address):
    """
    Get the real serial from the device.
    The `adb devices` output is ip:port if it is wireless connected.
    """
    if not is_ip_port(address):
        return address
    cmd = [adb, '-s', address, 'shell', 'getprop ro.boot.serialno']
    return subprocess.check_output(cmd, text=True).strip()


def get_device_name(adb, address):
    """
    Get the human readable device name.
    """
    cmds = [
        'settings get secure bluetooth_name',
        'getprop persist.sys.device_name',
        'settings get global device_name',
    ]
    for cmd in cmds:
        full_cmd = [adb, '-s', address, 'shell', cmd]
        output = subprocess.check_output(full_cmd, text=True).strip()
        if output and output != 'null':
            return output


def is_ip_port(address: str) -> bool:
    """Check whether a string is an IP:Port address."""
    return re.match(r'^\d+\.\d+\.\d+\.\d+:\d+$', address) is not None


if __name__ == '__main__':
    sys.exit(main())
