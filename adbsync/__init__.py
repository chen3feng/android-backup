import typing
from . import adb


__all__ = ['pull']


def pull(adb_path: str, serial: str,
         source_dirs: typing.List[str], target_dir: str, old_backup_dir: str,
         exclude_file: str):
    """
    Pull a file or directory from the device to the local filesystem.
    """
    adb_instance = adb.ADB(adb_path, serial)
    adb_instance.pull(source_dirs, target_dir, old_backup_dir, exclude_file)
