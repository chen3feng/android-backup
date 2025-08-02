import os
import posixpath
import shutil
import typing

import pathspec

DirScanResultType = typing.Tuple[typing.Dict[str, int], typing.Dict[str, typing.Tuple[int, float]]]


def scan_dir(root: str, subdir: str = "", filter: pathspec.PathSpec = None) -> DirScanResultType:
    """Scan a local directory and return a tuple of directories and files with their metadata."""
    dirs, files = {}, {}
    base = os.path.join(root, subdir)
    for dirpath, _, filenames in os.walk(base):
        rel_dirpath = os.path.relpath(dirpath, root).replace("\\", "/")
        try:
            if not filter.match_file(rel_dirpath):
                stat = os.stat(dirpath)
                dirs[rel_dirpath] = stat.st_mtime
            # else:
            #     print(f'Exclude {rel_dirpath}')
        except FileNotFoundError:
            # 目录可能在遍历过程中被删除
            pass
        for name in filenames:
            full_path = os.path.join(dirpath, name)
            rel_path = os.path.relpath(full_path, root).replace("\\", "/")
            if filter.match_file(rel_path):
                # print(f'Exclude {rel_path}')
                continue
            try:
                stat = os.stat(full_path)
                files[rel_path] = (stat.st_size, stat.st_mtime)
            except FileNotFoundError:
                # 文件可能在遍历过程中被删除
                continue
    return dirs, files


def makedirs(dirpath: str, timestamp: typing.Optional[float]) -> None:
    """Make directories and set the. timestamp."""
    if not os.path.exists(dirpath):
        os.makedirs(dirpath, exist_ok=True)
        if timestamp is not None:
            os.utime(dirpath, (timestamp, timestamp))


def sync_file(old_file: str, new_file: str, support_hardlink) -> bool:
    """Sync in local filesystem, use hardlink if it is supported."""
    if support_hardlink is not None:
        if support_hardlink:
            os.link(old_file, new_file)
        else:
            shutil.copy2(old_file, new_file)
    else:
        try:
            os.link(os.path.join(old_file), new_file)
        except OSError:
            print(f"[WARNING] Backup filesystem doesn't support hard link, use copy instead.")
            shutil.copy2(old_file, new_file)
            support_hardlink = False
    return support_hardlink


def remove_excluded(root, source_dir, filter: pathspec.PathSpec):
    """Remove files and directories that match the filter."""
    if not os.path.isdir(root):
        return
    if not source_dir:
        source_dir = ""
    full_path = posixpath.join(root, source_dir)
    for dirpath, dirnames, filenames in os.walk(full_path, topdown=False):
        # Remove files that match the filter
        dirpath = dirpath.replace("\\", "/")
        for name in filenames:
            rel_path = posixpath.relpath(posixpath.join(dirpath, name), root)
            if filter.match_file(rel_path):
                file_path = posixpath.join(dirpath, name)
                # print(f"Removing file: {file_path}")
                os.remove(file_path)
        # Remove directories that match the filter
        for name in dirnames:
            rel_path = posixpath.relpath(posixpath.join(dirpath, name), root)
            if filter.match_file(rel_path):
                dir_path = posixpath.join(dirpath, name)
                # print(f"Removing directory: {dir_path}")
                shutil.rmtree(dir_path, ignore_errors=True)
