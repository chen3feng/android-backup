import argparse
import importlib.util
import os
import posixpath
import subprocess
import sys
import types
import typing

from datetime import datetime
from importlib.machinery import SourceFileLoader

import adbsync


def main() -> int:
    config = load_config(os.path.join(os.path.dirname(__file__), 'global.conf'))
    if not config:
        print("No global configuration found.")
        return 1
    adb_path = config.ADB_PATH
    if not adb_path:
        adb_path = find_adb_path()
    if not adb_path:
        print("ADB_PATH not found in configuration or environment.")
        return 1

    print(f"Using adb path: {adb_path}")

    serial = find_device_serial(adb_path)
    if not serial:
        print("No device connected.")
        return 1

    print(f"Find device serial: {serial}")

    device_config_path = os.path.join(os.path.dirname(__file__), 'devices', f'{serial}.conf')
    if not os.path.exists(device_config_path):
        print(f"No configuration {device_config_path} found.")
        return 1
    device_config = load_config(device_config_path)
    if not device_config:
        print(f"Failed to load device configuration from {device_config_path}.")
        return 1
    print(f"Loaded device configuration: {device_config.DEVICE_NAME}")

    return pull_device(adb_path, serial, config, device_config)


def pull_device(adb_path, serial, config, device_config):
    device_backup_dir = posixpath.normpath(posixpath.join(config.BACKUP_BASE_DIR, device_config.BACKUP_DIR))
    multiple_versions = getattr(device_config, 'MULTIPLE_VERSIONS', False)
    if multiple_versions:
        # version_dir = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        version_dir = datetime.now().strftime("%Y-%m-%d")
        backup_dir = posixpath.join(device_backup_dir, version_dir)
        os.makedirs(backup_dir, exist_ok=True)
        latest_link_file, old_backup_dir = get_last_backup_dir(device_backup_dir)
    else:
        backup_dir = device_backup_dir
        old_backup_dir = None

    print(f'Pulling to {backup_dir}')
    for include_dir in device_config.INCLUDE_DIRS:
        parts = include_dir.split('/./')
        if len(parts) < 2:
            print(f"[ERROR] Invalid include directory format: {include_dir}, skipping.")
            continue
        root = parts[0]
        source_dir = parts[1]
        print(f"Pulling {posixpath.join(root, source_dir)}...")
        adbsync.pull(
            adb_path=adb_path,
            serial=serial,
            root=root,
            source_dir=source_dir,
            exclude_file=config.DEFAULT_EXCLUDE_FILE,
            target_dir=backup_dir,
            old_backup_dir=old_backup_dir
        )
    if multiple_versions:
        if update_latest(latest_link_file, version_dir):
            print(f"Updated latest link to {version_dir}")
        else:
            print(f"Failed to update latest link to {version_dir}")
            if sys.platform.startswith("win"):
                print("提示：Windows 上创建符号链接需要管理员权限或开启开发者模式")

    return 0


def get_last_backup_dir(device_backup_dir) -> typing.Tuple[str, typing.Optional[str]]:
    """
    Get the last backup directory from the latest symlink or file.
    If the symlink or file does not exist, return None.
    """
    latest_link_file = posixpath.join(device_backup_dir, 'latest')
    if os.path.exists(latest_link_file):
        if os.path.islink(latest_link_file):
            old_backup_dir = os.readlink(latest_link_file)
            if not os.path.isabs(old_backup_dir):
                old_backup_dir = posixpath.join(device_backup_dir, old_backup_dir)
            return latest_link_file, old_backup_dir
        with open(latest_link_file, 'r') as f:
            old_backup_dir = f.read().strip()
        if not os.path.isabs(old_backup_dir):
            old_backup_dir = posixpath.join(device_backup_dir, old_backup_dir)
        return latest_link_file, old_backup_dir
    return latest_link_file, None


def update_latest(link_file, version_dir) -> bool:
    """
    Update the latest symlink or file to point to the new version directory.
    """
    if os.path.exists(link_file):
        if os.path.islink(link_file):
            return update_link(link_file, version_dir)
        else:
            return create_link_file(link_file, version_dir)
    else:
        if not update_link(link_file, version_dir):
            return create_link_file(link_file, version_dir)
    return False


def create_link_file(link_file, version_dir) -> bool:
    try:
        with open(link_file, 'w') as f:
            f.write(version_dir)
            return True
    except OSError as e:
        print(f"[ERROR] Failed to create link file: {e}")
    return False


def update_link(link_file, version_dir) -> bool:
    try:
        if os.readlink(link_file) == version_dir:
            return True
        if os.path.islink(link_file) or os.path.exists(link_file):
            os.remove(link_file)
        os.symlink(version_dir, link_file,
                   target_is_directory=False)
        return True
    except OSError as e:
        pass
    return False


def load_config(config_file)-> typing.Optional[types.ModuleType]:
    """
    Load global configuration from a file.
    """
    try:
        config = SourceFileLoader("config_data", config_file).load_module()
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


def find_device_serial(adb: str) -> str:
    """
    Find the device serial number.
    This function should be implemented to retrieve the device serial number.
    """
    try:
        output = subprocess.check_output([adb, 'devices']).decode('utf-8')
        for line in output.splitlines():
            if '\tdevice' in line:
                return line.split('\t')[0]
    except subprocess.CalledProcessError as e:
        print(f"Error finding device serial: {e}")
    return ''


if __name__ == '__main__':
    sys.exit(main())
