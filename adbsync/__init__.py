import typing
from . import adb


__all__ = ['pull']


def pull(adb_path: str, serial: str,
         root: str, source_dir: str, target_dir: str, old_backup_dir: str,
         exclude_file: str):
    """
    Pull a file or directory from the device to the local filesystem.

    :param adb_path: Path to the adb executable.
    :param src: Source path on the device.
    :param dest: Destination path on the local filesystem.
    """
    adb_instance = adb.ADB(adb_path, serial)
    adb_instance.pull(root, source_dir, target_dir, old_backup_dir, exclude_file)
