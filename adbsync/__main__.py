import argparse
import sys

from . import pull

def parse_args():
    parser = argparse.ArgumentParser(
        description="Sync files from Android device via ADB, similar to rsync."
    )

    parser.add_argument(
        "--adb",
        metavar="ADB_PATH",
        default="adb",
        help="Path to adb executable (default: adb)",
    )

    parser.add_argument(
        "--device",
        metavar="DEVICE_ID",
        help="Specify device ID if multiple devices are connected",
    )

    parser.add_argument(
        "--link-dest",
        metavar="DIR",
        help="Hardlink unchanged files from this dir (like rsync)",
    )

    parser.add_argument(
        "--exclude-file",
        metavar="FILE",
        help="Path to file containing exclude patterns (one per line)",
    )

    # source_dirs 和 target_dir 都是位置参数
    parser.add_argument(
        "paths",
        metavar="PATH",
        nargs="+",
        help="Source directories followed by target directory",
    )

    args = parser.parse_args()

    if len(args.paths) < 2:
        parser.error("Need at least one source directory and one target directory.")

    # 拆分 source_dirs 和 target_dir
    args.source_dirs = args.paths[:-1]
    args.target_dir = args.paths[-1]
    del args.paths

    return args


def main():
    args = parse_args()
    return pull(
        adb_path=args.adb, address=args.device,
        source_dirs=args.source_dirs, target_dir=args.target_dir, old_backup_dir=args.link_dest,
        exclude_file=args.exclude_file)


if __name__ == '__main__':
    sys.exit(main())
