import argparse
import collections
import importlib.util
import os
import posixpath
import pprint
import re
import subprocess
import sys
import types
import typing

from datetime import datetime
from importlib.machinery import SourceFileLoader

import adbsync


Device = collections.namedtuple('Device', ['address', 'serial', 'name'])


def main() -> int:
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

    if not add_devices_config(devices):
        print(1234)
        return 1

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


def add_devices_config(devices: typing.List[Device]) -> bool:
    print('Add devices')
    for device in devices:
        config_path = os.path.join(os.path.dirname(__file__), 'devices', f'{device.serial}.conf')
        if os.path.exists(config_path):
            print(f'config_path {config_path} already exists')
            continue
        if not create_config(config_path, device):
            return False
    return True


DEFAULT_INCLUDE_DIRS = [
    # The path contains the root directory and the source directory.
    # They are separated by /./.
    # For example:
    # Sync the Documents directory to local Documents under the backup directory.
    "/sdcard/./Documents",
    "/sdcard/./DCIM",
    "/sdcard/./Documents",
    "/sdcard/./Download",
    "/sdcard/./Movies",
    "/sdcard/./Music",
    "/sdcard/./Pictures",

    # The directory can also be a subdirectory
    # The follow lines sync QQ and Weixin files to tencent directory under the backup directory.
    "/sdcard/./tencent/qqfile_recv",
    "/sdcard/./tencent/micromsg/weixin",
]

def create_config(config_path: str, device: Device) -> bool:
    print(f'config_path={config_path}')
    with open(config_path, 'w', encoding='utf8') as f:
        print(f'BACKUP_DIR = "{device.name}"', file=f)
        print(f'INCLUDE_DIRS = {pprint.pformat(DEFAULT_INCLUDE_DIRS, indent=4)}', file=f)
    return True


def pull_device(adb_path, device, config, device_config):
    device_backup_dir = posixpath.normpath(posixpath.join(config.BACKUP_BASE_DIR, device_config.BACKUP_DIR))
    print(f'Backup device {device.name} to {device_backup_dir}')
    multiple_versions = getattr(device_config, 'MULTIPLE_VERSIONS', False)
    if multiple_versions:
        # version_dir = datetime.now().strftime("%Y-%m-%d_%H%M%S")
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
        with open(latest_file, 'r') as f:
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
    if os.path.exists(latest_file):
        if os.path.islink(latest_file):
            if os.readlink(latest_file) == version_dir:
                return True
            os.remove(latest_file)
    try:
        os.symlink(version_dir, latest_file, target_is_directory=False)
        return True
    except OSError as e:
        pass
    return False


def update_tag_file(latest_file, version_dir) -> bool:
    """Update the target path in a tag file."""
    try:
        with open(latest_file, 'w') as f:
            f.write(version_dir)
            return True
    except OSError as e:
        print(f"[ERROR] Failed to create link file: {e}")
    return False


def load_config(name, config_file)-> typing.Optional[types.ModuleType]:
    """
    Load global configuration from a file.
    The name should be unique otherwise it returns existing one.
    """
    try:
        config = SourceFileLoader(name, config_file).load_module()
        return config
    except Exception as e:
        print(f"Error loading configuration from {config_file}: {e}")
        return None


def find_adb_path() -> str:
    """
    Find the adb executable path.
    This function should be implemented to locate the adb executable.
    """
    if os.name == 'nt':
        if subprocess.call(['where', 'adb'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
            adb_path = subprocess.check_output(['where', 'adb']).decode('utf-8').strip().splitlines()[0]
            return adb_path
        if os.environ.get('ANDROID_HOME'):
            adb_path = os.path.join(os.environ['ANDROID_HOME'], 'platform-tools', 'adb.exe')
            if os.path.exists(adb_path):
                return adb_path
    else:  # Assuming a Unix-like system
        if subprocess.call(['which', 'adb'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
            adb_path = subprocess.check_output(['which', 'adb']).decode('utf-8').strip()
            return adb_path
        if os.environ.get('ANDROID_HOME'):
            adb_path = os.path.join(os.environ['ANDROID_HOME'], 'platform-tools', 'adb')
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
    if not is_ip_port(address):
        return address
    cmd = [adb, '-s', address, 'shell', 'getprop ro.boot.serialno']
    return subprocess.check_output(cmd, text=True).strip()


def get_device_name(adb, address):
    cmds = [
        'settings get secure bluetooth_name',
        'getprop persist.sys.device_name',
        'settings get global device_name',
        # 'getprop ro.product.marketname',
        # 'getprop ro.product.odm.marketname',
        # 'getprop ro.product.vendor.marketname',
    ]
    for cmd in cmds:
        full_cmd = [adb, '-s', address, 'shell', cmd]
        output = subprocess.check_output(full_cmd, text=True).strip()
        if output and output != 'null':
            return output

def is_ip_port(address: str) -> bool:
    return re.match(r'^\d+\.\d+\.\d+\.\d+:\d+$', address) is not None


if __name__ == '__main__':
    sys.exit(main())
