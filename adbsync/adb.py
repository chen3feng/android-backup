import os
import posixpath
import shutil
import subprocess
import sys
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
        return pathspec.PathSpec([])
    with open(exclude_file, 'r', encoding='utf-8') as fh:
        spec = pathspec.PathSpec.from_lines('gitwildmatch', fh)
        return spec


class ADB():
    def __init__(self, adb: str, device: str = ""):
        self.adb = adb
        self.device = device

    def call(self, cmd: typing.List[str], *args, **kwargs) -> int:
        full_cmd = self.extend_cmd(cmd)
        # print(f"Calling command: {' '.join(full_cmd)}")
        kwargs.setdefault('errors', 'replace')
        return subprocess.call(full_cmd, *args, **kwargs)

    def run(self, cmd: typing.List[str], *args, **kwargs) -> subprocess.CompletedProcess:
        full_cmd = self.extend_cmd(cmd)
        # print(f"Running command: {' '.join(full_cmd)}")
        kwargs.setdefault('errors', 'replace')
        return subprocess.run(full_cmd, *args, **kwargs)

    def check_output(self, cmd: typing.List[str], *args, **kwargs) -> str:
        full_cmd = self.extend_cmd(cmd)
        # print(f"Running output command: {' '.join(full_cmd)}")
        kwargs.setdefault('errors', 'replace')
        return subprocess.check_output(full_cmd, text=True, *args, **kwargs)

    def extend_cmd(self, cmd: typing.List[str]) -> typing.List[str]:
        full_cmd = [self.adb]
        if self.device:
            full_cmd.extend(['-s', self.device])
        full_cmd.extend(cmd)
        return full_cmd

    def pull(self, source_dirs, target_dir, old_backup_dir, exclude_file):
        exclude = load_exclude_file(exclude_file)
        for include_dir in source_dirs:
            parts = include_dir.split('/./')
            if len(parts) < 2:
                print(f"[ERROR] Invalid include directory format: {include_dir}, skipping.")
                continue
            self.pull_one_dir(
                root=parts[0],
                source_dir=parts[1],
                target_dir=target_dir,
                old_backup_dir=old_backup_dir,
                exclude_path=exclude.match_file,
            )

    def pull_one_dir(self, root, source_dir, target_dir, old_backup_dir, exclude_path):
        print(f"Pulling {posixpath.join(root, source_dir)}...")
        try:
            remote_dirs, remote_files = self.scan_remote_dir(root, source_dir, exclude_path)
        except subprocess.CalledProcessError:
            print(f"Failed to scan remote directory {source_dir}")
            return

        if local_fs.is_valid_old_backup_dir(old_backup_dir, target_dir):
            self.local_sync(old_backup_dir, remote_dirs, remote_files, target_dir, source_dir)

        self.pull_dirs(root, remote_dirs, target_dir, exclude_path)
        self.pull_files(root, remote_dirs, remote_files, target_dir)

    def scan_remote_dir(self, root, source_dir, exclude_path) -> typing.Tuple[dict, dict]:
        """Scan remote dir, obtain all. its dir and files names and attributes"""
        full_dir = posixpath.join(root, source_dir)
        find_cmd = self.get_find_command(full_dir)
        cmd = ['shell', find_cmd]
        output = self.check_output(cmd)
        dirs, files = self.parse_find_output(root, source_dir, output, exclude_path)
        self.remove_empty_dirs(dirs, files)
        return dirs, files

    def get_find_command(self, full_dir: str) -> str:
        # Use the `find` command to recursively list all files and non-empty directories.
        # For each entry, print:
        #   - File mode (%M)
        #   - Size in bytes (%s)
        #   - Modification timestamp (%T@)
        #   - Relative path (%P), enclosed in slashes: |/absolute/path|
        #
        # Wrapping the relative path in pipes makes it easier to:
        #   - Unambiguously detect blank or whitespace-containing paths
        #   - Treat the root directory (empty %P) consistently as `||`
        if self.find_support_printf():
            return rf'find "{full_dir}" \( -type f -or -type d ! -empty \) -printf "%M %s %T@ |%p|\n"'
        else:
            exec_cmd = r'stat -c "%A %s %Y |%n|" {} \;'
            return rf'find "{full_dir}" \( -type f -or -type d ! -empty \) -exec {exec_cmd}'
    
    def find_support_printf(self) -> bool:
        find_cmd = 'find /bin -maxdepth 1 -printf ""'
        cmd = ['shell', find_cmd]
        return self.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0

    def parse_find_output(self, source_dir, output, exclude_path):
        """Parse the output of the `find` command, return all dir and file attributes."""
        dirs, files = {}, {}
        for line in output.splitlines():
            parts = line.strip().split(" ", 3)
            if len(parts) != 4:
                # Some exceptional case, there are '\n' characters in the path
                print(f'Skip invalid line "{line}"')
                continue
            mode = parts[0]
            size = int(parts[1])
            mtime = float(parts[2])
            path = parts[3].strip('|') # Remove the enclosing slashes, see `get_find_command`
            prefix = posixpath.join(root, source_dir)
            path = path.removeprefix(prefix)
            path = path.removeprefix('/')
            if not exclude_path(path):
                rel_path = posixpath.join(source_dir, path) if path else source_dir
                if mode.startswith('d'):
                    dirs[rel_path] = mtime
                else:
                    files[rel_path] = (size, mtime)
        return dirs, files

    def remove_empty_dirs(self, dirs, files):
        """Remove all dirs which no file to be synced under them."""
        non_empty = set()
        for f in files:
            # Add all parents of each file to non_empty set
            d = posixpath.dirname(f)
            while d:
                non_empty.add(d)
                d = posixpath.dirname(d)
        empty = dirs.keys() - non_empty
        for d in empty:
            dirs.pop(d)

    def local_sync(self, old_backup_dir, remote_dirs, remote_files, target_dir, source_dir):
        """Sync file from old backup."""
        print(f'Syncing {posixpath.join(old_backup_dir, source_dir)} to {target_dir}')
        support_hardlink = None
        progress_printed = False
        progress_time = datetime.now()
        for i, (file, (size, mtime)) in enumerate(remote_files.items()):
            # Show progress
            now = datetime.now()
            if (now - progress_time).total_seconds() > 1:
                print(f'\rProgress: {i+1}/{len(remote_files)}', end='', flush=True)
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


    def pull_dirs(self, root, remote_dirs, target_dir, exclude_path):
        """Pull directories from the remote device to the target directory."""
        # Remove directories that match the exclude_path
        pull_dirs = self.get_pull_dirs(remote_dirs, target_dir)
        for pull_dir in pull_dirs:
            if not exclude_path(pull_dir):
                self.pull_dir(root, pull_dir, target_dir, remote_dirs, exclude_path)

    def get_pull_dirs(self, remote_dirs, target_dir):
        """Get the pull command for a directory."""
        # Ensure the target directory exists
        pull_dirs = []
        for remote_dir in remote_dirs:
            local_dir = posixpath.join(target_dir, remote_dir)
            if not os.path.exists(local_dir):
                pull_dirs.append(remote_dir)
        return remove_nested_dirs(pull_dirs)

    def pull_dir(self, root, source_dir, target_dir, remote_dirs, exclude_path):
        """Pull a directory from the device."""
        print(f'Pulling {source_dir}')
        # Construct the pull command
        # Note the use of '-a' to preserve file attributes
        # Add a slash after the source dir to pull the whole directory.
        # The target directory is the parent directory of the source_dir to ensure the structure is maintained.
        parent_dir = posixpath.dirname(source_dir)
        dest_dir = posixpath.join(target_dir, parent_dir)
        local_fs.makedirs(dest_dir, remote_dirs.get(parent_dir))
        cmd = ['pull', '-a', posixpath.join(root, source_dir) + '/', dest_dir]
        self.call(cmd)
        # adb pull doesn't support exclude option, remove excluded files from the target_dir after download.
        local_fs.remove_excluded(target_dir, source_dir, exclude_path)

    def pull_files(self, root, remote_dirs, files, target_dir):
        """Pull files from the remote device to the target directory."""
        files = self.get_pull_files(files, target_dir)
        ret = 0
        for file_path in files:
            ret = self.pull_one_file(root, remote_dirs, file_path, target_dir) or ret
        return ret

    def pull_one_file(self, root, remote_dirs, file_path, target_dir):
        """Pull one file from remote to local."""
        remote_path = posixpath.join(root, file_path)
        local_path = posixpath.join(target_dir, file_path)
        parent_dir = posixpath.dirname(file_path)
        if parent_dir not in remote_dirs:
            # Maybe caused by CHinese messy code
            print(f'Remote dir {parent_dir} does not in remote_dirs')
            return 1
        local_fs.makedirs(posixpath.join(target_dir, parent_dir), remote_dirs[parent_dir])
        # On windows, some Chinese filenames can be truncated when the target file name is not specified explicitly.
        # Always specify the full filename rather than only the target directory.
        cmd = ['pull', '-a', remote_path, local_path]
        if os.name != 'nt':
            return self.call(cmd)

        # On windows, ADB can't handle some Chinese target path correctly,
        # retry with pulling to current dir and move to the target dir.
        ret = self.run(cmd, stderr=subprocess.PIPE, text=True)
        if ret.returncode == 0:
            return 0
        if 'cannot create file/directory' in ret.stderr:
            file_name = posixpath.basename(file_path)
            cmd = ['pull', '-a', remote_path, file_name]
            if self.call(cmd) == 0:
                shutil.move(file_name, local_path)
            return 0
        sys.stderr.write(ret.stderr)
        return 1

    def get_pull_files(self, remote_files, target_dir):
        """Get the remote files need to be pulled to local."""
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
