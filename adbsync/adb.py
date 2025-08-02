import itertools
import os
import posixpath
import shlex
import shutil
import subprocess
import typing

from datetime import datetime

import pathspec

from . import local_fs


def remove_nested_dirs(dirs):
    """Remove nested directories from the list."""
    dirs = sorted(set(posixpath.normpath(d) for d in dirs))
    result = []

    for i, dir_i in enumerate(dirs):
        for j in range(i):
            # 如果前面的某个目录是它的祖先，就跳过
            if posixpath.commonpath([dirs[j], dir_i]) == dirs[j]:
                break
        else:
            result.append(dir_i)
    return result


def load_exclude_file(exclude_file: str) -> pathspec.PathSpec:
    if not exclude_file:
        return pathspec.PathSpec()
    with open(exclude_file, 'r') as fh:
        spec = pathspec.PathSpec.from_lines('gitwildmatch', fh)
        return spec


class ADB():
    def __init__(self, adb: str, device: str = None):
        self.adb = adb
        self.device = device

    def run(self, cmd: typing.List[str], *args, **kwargs) -> int:
        full_cmd = self.extend_cmd(cmd)
        # print(f"Running command: {' '.join(full_cmd)}")
        return subprocess.call(full_cmd, *args, **kwargs)

    def check_output(self, cmd: typing.List[str], *args, **kwargs) -> str:
        full_cmd = self.extend_cmd(cmd)
        # print(f"Running command: {' '.join(full_cmd)}")
        return subprocess.check_output(full_cmd, text=True, *args, **kwargs)

    def extend_cmd(self, cmd: typing.List[str]) -> typing.List[str]:
        full_cmd = [self.adb]
        if self.device:
            full_cmd.extend(['-s', self.device])
        full_cmd.extend(cmd)
        return full_cmd

    def shell(self, cmd) -> int:
        return self.run(['shell'] + [cmd])

    def pull(self, root, source_dir, target_dir, old_backup_dir, exclude_file):
        filter = load_exclude_file(exclude_file)
        try:
            remote_dirs, remote_files = self.scan_remote_dir(root, source_dir, filter)
        except subprocess.CalledProcessError:
            print(f"Failed to scan remote directory {source_dir}")
            return

        if old_backup_dir:
            self.local_sync(old_backup_dir, remote_dirs, remote_files, target_dir, source_dir, filter)

        self.pull_dirs(root, remote_dirs, target_dir, filter)
        self.pull_files(root, remote_dirs, remote_files, target_dir)

    def scan_remote_dir(self, root, source_dir, filter):
        # TODO: call find only once
        find_cmd = ['find', posixpath.join(root, source_dir), '-type', 'f', '-printf', '%s %T@ %P\n']
        cmd = ['shell', " ".join(shlex.quote(a) for a in find_cmd)]
        output = self.check_output(cmd)
        files = self.parse_find_file_outout(root, source_dir, output, filter)

        find_cmd = ['find', posixpath.join(root, source_dir), '-type', 'd', '-printf', '%T@ %P\n']
        cmd = ['shell', " ".join(shlex.quote(a) for a in find_cmd)]
        output = self.check_output(cmd)
        dirs = self.parse_find_dir_output(root, source_dir, output, filter)

        return dirs, files

    def print_files(self, files):
        for path, (size, mtime) in itertools.islice(files.items(), 10):
            print(f"{path}: {size} bytes, modified at {mtime}")

    def parse_find_dir_output(self, root, source_dir, output, filter):
        result = {}
        for line in output.splitlines():
            parts = line.strip().split(" ", 1)
            try:
                mtime = float(parts[0])
            except:
                # Skip abnormal path such as '.\n=UnchNGa'
                continue
            if len(parts) == 1:
                # The source_dir itself
                result[source_dir] = mtime
                continue
            path = parts[1]
            if not filter.match_file(path):
                result[posixpath.join(source_dir, path)] = mtime
        return result

    def parse_find_file_outout(self, root, source_dir, output, filter):
        result = {}
        for line in output.splitlines():
            parts = line.strip().split(" ", 2)
            if len(parts) < 3:
                raise ValueError(f"Line not in expected format: {line}")
            size = int(parts[0])
            mtime = float(parts[1])
            path = parts[2]
            if not filter.match_file(path):
                result[posixpath.join(source_dir, path)] = (size, mtime)
        return result

    def local_sync(self, old_backup_dir, remote_dirs, remote_files, target_dir, source_dir, filter):
        """Sync file from old backup."""
        if not os.path.isdir(old_backup_dir):
            return
        if posixpath.realpath(old_backup_dir) == posixpath.realpath(target_dir):
            return
        print(f'Syncing {old_backup_dir} to {target_dir}')
        support_hardlink = None
        progress_printed = False
        progress_time = datetime.now()
        for i, (file, (size, mtime)) in enumerate(remote_files.items()):
            # Show progress
            now = datetime.now()
            if (now - progress_time).total_seconds() > 1:
                print(f'\rProgress: {i}/{len(remote_files)}', end='', flush=True)
                progress_printed = True
                progress_time = now

            of_path = os.path.join(old_backup_dir, file)
            if not os.path.exists(of_path):
                continue
            of = os.stat(of_path)
            if of.st_size != size or abs(mtime - of.st_mtime) > 2:
                continue
            target_file = os.path.join(target_dir, file)
            if os.path.exists(target_file):
                tf = os.stat(target_file)
                if of.st_size == tf.st_size and abs(of.st_mtime - tf.st_mtime) < 2:
                    continue
            # print(f'Linking {file}')
            target_file_dir = os.path.dirname(target_file)
            local_fs.makedirs(target_file_dir, remote_dirs[posixpath.dirname(file)])

            old_file = os.path.join(old_backup_dir, file)
            new_file = os.path.join(target_dir, file)
            support_hardlink = local_fs.sync_file(old_file, new_file, support_hardlink)

        if progress_printed:
            print('')


    def pull_dirs(self, root, remote_dirs, target_dir, filter):
        """Pull directories from the remote device to the target directory."""
        # Remove directories that match the filter
        pull_dirs = self.get_pull_dirs(remote_dirs, target_dir)
        for pull_dir in pull_dirs:
            if not filter.match_file(pull_dir):
                self.pull_dir(root, pull_dir, target_dir, remote_dirs, filter)

    def get_pull_dirs(self, remote_dirs, target_dir):
        """Get the pull command for a directory."""
        # Ensure the target directory exists
        pull_dirs = []
        for remote_dir in remote_dirs:
            local_dir = posixpath.join(target_dir, remote_dir)
            if not os.path.exists(local_dir):
                pull_dirs.append(remote_dir)
        return remove_nested_dirs(pull_dirs)

    def pull_dir(self, root, source_dir, target_dir, remote_dirs, filter):
        # Construct the pull command
        # Note the use of '-a' to preserve file attributes
        # The target directory is the parent directory of the source_dir to ensure the structure is maintained.
        # `adb pull source_dir/ target_dir` way does not work as expected because it creates a new subdirectory in target_dir if the target_dir already exist.
        dest_dir = os.path.join(target_dir, source_dir)
        local_fs.makedirs(dest_dir, remote_dirs.get(source_dir))
        cmd = ['pull', '-a', posixpath.join(root, source_dir), dest_dir]
        self.run(cmd)
        local_fs.remove_excluded(target_dir, source_dir, filter)

    def pull_files(self, root, remote_dirs, files, target_dir):
        """Pull files from the remote device to the target directory."""
        files = self.get_pull_files(files, target_dir)
        for f in files:
            ff = posixpath.join(root, f)
            dest_dir = posixpath.join(target_dir, posixpath.dirname(f))
            local_fs.makedirs(dest_dir, remote_dirs[posixpath.dirname(f)])
            cmd = ['pull', '-a', ff, dest_dir]
            self.run(cmd)

    def get_pull_files(self, remote_files, target_dir):
        result = []
        for path, (rf_size, rf_mtime) in remote_files.items():
            local_path = os.path.join(target_dir, path)
            if not os.path.exists(local_path):
                result.append(path)
                continue
            lf = os.stat(local_path)
            if rf_size != lf.st_size or abs(rf_mtime - lf.st_mtime) > 2:
                result.append(path)
        return result
