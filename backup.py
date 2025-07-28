import argparse
import importlib.util
from importlib.machinery import SourceFileLoader
import os
import subprocess
import types
import typing

import adbsync


def main():
    config = load_config(os.path.join(os.path.dirname(__file__), 'global.conf'))
    if not config:
        print("No global configuration found.")
        return
    adb_path = config.ADB_PATH
    if not adb_path:
        adb_path = find_adb_path()
    if not adb_path:
        print("ADB_PATH not found in configuration or environment.")
        return

    serial = find_device_serial(adb_path)
    if not serial:
        print("No device connected.")
        return

    print(f"Find device serial: {serial}")

    device_config_path = os.path.join(os.path.dirname(__file__), 'devices', f'{serial}.conf')
    if not os.path.exists(device_config_path):
        print(f"No configuration {device_config_path} found.")
        return
    device_config = load_config(device_config_path)
    if not device_config:
        print(f"Failed to load device configuration from {device_config_path}.")
        return
    print(f"Loaded device configuration: {device_config.DEVICE_NAME}")

    for root, source_dir in device_config.INCLUDE_DIRS:
        adbsync.pull(
            adb_path=adb_path,
            serial=serial,
            root=root,
            source_dir=source_dir,
            exclude_file=config.DEFAULT_EXCLUDE_FILE,
            target_dir=os.path.join(config.BACKUP_BASE_DIR, device_config.DEVICE_NAME),
            old_backup_dir=device_config.DEVICE_NAME
        )


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
    adb_path = 'adb'  # Default to 'adb' if not specified
    return adb_path


def find_device_serial(adb: str) -> str:
    """
    Find the device serial number.
    This function should be implemented to retrieve the device serial number.
    """
    print(f"Finding device serial using adb: {adb}")
    try:
        output = subprocess.check_output([adb, 'devices']).decode('utf-8')
        for line in output.splitlines():
            if '\tdevice' in line:
                return line.split('\t')[0]
    except subprocess.CalledProcessError as e:
        print(f"Error finding device serial: {e}")
    return ''


if __name__ == '__main__':
    main()
