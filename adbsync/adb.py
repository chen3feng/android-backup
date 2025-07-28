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
        cmd = ['pull', os.path.join(root, source_dir), os.path.join(target_dir, source_dir)]
        return self.run(cmd)

class RemoteFiles:
    pass
