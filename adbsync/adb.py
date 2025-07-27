import subprocess
import typing

class ADB():
    def __init__(self, adb: str, device: str = None):
        self.adb = adb
        self.device = device

    def run(self, cmd:[str]) -> int:
        full_cmd = [self.adb]
        if self.device:
            full_cmd.extend(['-s', self.device])
        return subprocess.call(full_cmd)

    def shell(self, cmd) -> int:
        return self.run(['shell'] + [cmd])

    def pull(self, src, dest, args: Optional[list[str]]=None):
        args = args or []
        return self.run(['pull'] + args + [src, dest])

class RemoteFiles:
    pass
