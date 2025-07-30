import itertools
import os
import shlex
import subprocess
import typing

import pathspec

DirScanResultType = typing.Tuple[typing.Dict[str, int], typing.Dict[str, typing.Tuple[int, float]]]

def scan_local_dir(root: str, subdir: str = "", filter: pathspec.PathSpec = None) -> DirScanResultType:
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
        print(f'Pulling {source_dir}...')
        filter = load_exclude_file(exclude_file)
        remote_dirs, remote_files = self.scan_remote_dir(root, source_dir, filter)
        local_dirs, local_files = scan_local_dir(target_dir, source_dir, filter)
        pull_files = self.get_pull_files(remote_files, local_files)
        # self.pull_dir(root, source_dir, target_dir, old_backup_dir, filter)
        self.pull_files(root, pull_files, target_dir)

    def scan_remote_dir(self, root, source_dir, filter):
        # TODO: call find only once
        find_cmd = ['find', os.path.join(root, source_dir), '-type', 'f', '-printf', '%s %T@ %P\n']
        cmd = ['shell', " ".join(shlex.quote(a) for a in find_cmd)]
        output = self.check_output(cmd)
        files = self.parse_find_file_outout(root, source_dir, output, filter)

        find_cmd = ['find', os.path.join(root, source_dir), '-type', 'd', '-printf', '%T@ %P\n']
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
            if len(parts) < 2:
                # The source_dir itself
                continue
            mtime = float(parts[0])
            path = parts[1]
            if not filter.match_file(path):
                result[os.path.join(source_dir, path)] = mtime
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
                result[os.path.join(source_dir, path)] = (size, mtime)
        return result

    def get_pull_files(self, remote_files, local_files):
        result = []
        for path, (rf_size, rf_mtime) in remote_files.items():
            lf = local_files.get(path)
            if not lf:
                result.append(path)
                continue
            lf_size, lf_mtime = lf
            if rf_size != lf_size or abs(rf_mtime - lf_mtime) > 2:
                result.append(path)
        return result

    def remove_excluded(self, root, source_dir, filter: pathspec.PathSpec) -> int:
        pass

    def pull_dir(self, root, source_dir, target_dir, old_backup_dir, filter):
        # Construct the pull command
        # Note the use of '-a' to preserve file attributes
        # The target directory is the parent directory of the source_dir to ensure the structure is maintained.
        # `adb pull source_dir/ target_dir` way does not work as expected because it creates a new subdirectory in target_dir if the target_dir already exist.
        dest_dir = os.path.dirname(os.path.join(target_dir, source_dir))
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
        cmd = ['pull', '-a', os.path.join(root, source_dir), dest_dir]
        self.run(cmd)
        self.remove_excluded(target_dir, source_dir, filter)

    def pull_files(self, root, files, target_dir):
        for f in files:
            ff = os.path.join(root, f)
            dest_dir = os.path.join(target_dir, os.path.dirname(f))
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)
            cmd = ['pull', '-a', ff, dest_dir]
            self.run(cmd)
