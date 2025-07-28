import os
import subprocess
import typing

class ADB():
    def __init__(self, adb: str, device: str = None):
        self.adb = adb
        self.device = device

    def run(self, cmd: typing.List[str]) -> int:
        full_cmd = [self.adb]
        if self.device:
            full_cmd.extend(['-s', self.device])
        full_cmd.extend(cmd)
        print(f"Running command: {' '.join(full_cmd)}")
        return subprocess.call(full_cmd)

    def shell(self, cmd) -> int:
        return self.run(['shell'] + [cmd])

    def pull(self, root, source_dir, target_dir, old_backup_dir, exclude_file):
        # Construct the pull command
        # Note the use of '-a' to preserve file attributes
        # The target directory is the parent directory of the source_dir to ensure the structure is maintained.
        # `adb pull source_dir/ target_dir` way does not work as expected because it creates a new subdirectory in target_dir if the target_dir already exist.
        dest_dir = os.path.dirname(os.path.join(target_dir, source_dir))
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
        cmd = ['pull', '-a', os.path.join(root, source_dir), dest_dir]
        return self.run(cmd)

class RemoteFiles:
    pass
