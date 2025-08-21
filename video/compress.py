#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Compress video files on Android device using ffmpeg.
This script will compress the video files on the Android device using ffmpeg.
It will use the best available encoder according to the system and ffmpeg configuration.
The compressed video will be pushed back to the device with the original timestamp.
"""

import argparse
import enum
import subprocess
import os
import stat
import sys
import tempfile
import textwrap
import typing
from datetime import datetime

from info import get_video_info


MB = 1024*1024
QUALITY_CHOICES = ["high", "medium", "low"]


encoder_quality = {
    "hevc_videotoolbox": {
        "high":   ["-b:v", "8M"],
        "medium": ["-b:v", "5M"],
        "low":    ["-b:v", "3M"],
    },
    "hevc_nvenc": {
        "high":   ["-cq", "18", "-preset", "slow"],
        "medium": ["-cq", "23", "-preset", "medium"],
        "low":    ["-cq", "28", "-preset", "fast"],
    },
    "hevc_qsv": {
        "high":   ["-global_quality", "23", "-preset", "slow"],
        "medium": ["-global_quality", "28", "-preset", "medium"],
        "low":    ["-global_quality", "32", "-preset", "fast"],
    },
    "hevc_amf": {
        "high":   ["-quality", "high", "-rc", "vbr"],
        "medium": ["-quality", "balanced", "-rc", "vbr"],
        "low":    ["-quality", "speed", "-rc", "vbr"],
    },
    "libx265": {
        "high":   ["-crf", "18", "-preset", "slow"],
        "medium": ["-crf", "23", "-preset", "medium"],
        "low":    ["-crf", "28", "-preset", "fast"],
    },
}


def get_encoder_quality(encoder: str, quality: str) -> typing.List[str]:
    """Get the encoder quality settings."""
    if encoder not in encoder_quality:
        return []
    if quality not in encoder_quality[encoder]:
        return []
    return encoder_quality[encoder][quality]


def compress_video_ffmpeg(input_path: str, output_path: str, quality: str) -> int:
    """Compress a video file using ffmpeg with the specified quality."""

    encoder = get_best_encoder()
    quality_params = get_encoder_quality(encoder, quality)

    cmd = [
        "ffmpeg",
        "-y", "-v", "error", "-stats",
        "-i", input_path,
        "-c:v", encoder,
        "-pix_fmt", "yuv420p",
        "-profile:v", "main",
        "-tag:v", "hvc1",
    ] + quality_params + [
        "-c:a", "copy",
        "-movflags", "+faststart",
        "-map", "0", # Keep somthing like subtitle
        "-map_metadata", "0",   # Copy all metadata
        output_path
    ]
    # print(f"Running command: {cmd}")
    returncode = subprocess.call(cmd)
    if returncode != 0:
        return returncode
    # Copy all exif infomation.
    cmd = ["exiftool", "-tagsFromFile", input_path, "-all:all", "-unsafe", output_path]
    return subprocess.call(cmd, stdout=subprocess.DEVNULL)


# Save the best encoder globally to avoid checking every time
BEST_ENCODER : typing.Optional[str] = None

def get_best_encoder() -> str:
    """Get the best vodeo encoder according the system and ffmpeg configuration."""
    global BEST_ENCODER # pylint: disable=global-statement
    if BEST_ENCODER is None:
        if sys.platform == 'darwin':
            BEST_ENCODER = check_encoders(["hevc_videotoolbox"])
        else:
            BEST_ENCODER = check_encoders(["hevc_nvenc", "hevc_qsv", "hevc_amf"])
    return BEST_ENCODER


def check_encoders(encoders: typing.List[str], default: str='libx265') -> str:
    """Check whether the encoder is available, return the first available one."""
    for encoder in encoders:
        if is_encoder_available(encoder):
            print(f"Using hardware accelerated H.265 encoder: {encoder}")
            return encoder
    print(f"No suitable encoder found, using default: {default}")
    return default


def is_encoder_available(name: str) -> bool :
    """Test whether the encoder is available."""
    cmd = [
        "ffmpeg", "-y", "-t", "0.1", "-f", "lavfi",
        "-i", "testsrc=duration=0.1:size=1280x720:rate=30",
        "-c:v", name, "-preset", "fast",
        "-f", "mp4", os.path.devnull
    ]
    return subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def get_target_bitrate(video_info: dict, quality: str) -> int:
    """Calculate the target bitrate for compression based on video resolution."""
    # For a 1920x1080, 30FPS, HEVC (H.265) video, the suitable bitrate depends for quality :
    #
    # Purpose / Quality     Bitrate       Notes
    # ----------------------------------------------------------------------
    # High Quality          15–20 Mbps    For archiving, re-editing, or professional use
    # Premium Playback      8–12 Mbps     Blu-ray like quality, minimal visible compression
    # Standard Web Upload   4–6 Mbps      Common range for Online Video Platforms
    # Maximum Compression   2–3 Mbps      Suitable for IM sharing,with detail loss
    quality_bitrate = {
        "high": 4,      # 8 Mbps
        "medium": 2.5,  # 5 Mbps
        "low": 1.5,     # 3 Mbps
    }
    # The target bitrate also depends on video resolution
    area = video_info["width"] * video_info["height"]
    return int(area * quality_bitrate[quality])


def adb_pull_file(device_path: str, local_path: str) -> int:
    """Pull a file from the Android device to the local machine."""
    # The `-a` option make the file time synced
    return subprocess.call(["adb", "pull", "-a", device_path, local_path])


def adb_push(local_path: str, device_path: str, timestamp: float) -> int:
    """Push a file to the Android device and set its timestamp."""
    print("Pushing back compressed file to device.")
    returncode = subprocess.call(["adb", "push", local_path, device_path])
    if returncode != 0:
        return returncode
    if timestamp == 0.0:
        return 0
    dt = datetime.fromtimestamp(timestamp)
    touch_time = dt.strftime("%Y%m%d%H%M.%S")

    cmd = f"touch -t {touch_time} {device_path}"
    return subprocess.call(["adb", "shell", cmd], stdout=subprocess.DEVNULL)


class CompressResult(enum.Enum):
    Success = 1
    Skipped = 2
    Failure = 3

def compress_remote_video(full_path: str, tmpdir: str, quality: str, dry_run: bool) -> CompressResult:
    """Compress a remote video file."""
    local_original = os.path.join(tmpdir, "original.mp4")
    local_compressed = os.path.join(tmpdir, "compressed.mp4")

    if adb_pull_file(full_path, local_original) != 0:
        return CompressResult.Failure

    video_info = get_video_info(local_original)

    if not need_to_compress(video_info, quality):
        print('File is already compressed at the expected quality.')
        return CompressResult.Skipped

    print("Compressing file...")
    if compress_video_ffmpeg(local_original, local_compressed, quality) != 0:
        return CompressResult.Failure

    compressed_size = os.path.getsize(local_compressed)
    original_size = os.path.getsize(local_original)
    compression_ratio = compressed_size / original_size
    print(f"Compression ratio: {compressed_size}/{original_size} = {compression_ratio:.2%}")
    if compression_ratio > 0.95:
        print(f"File is not effectively compressed, skipping push.")
        return CompressResult.Skipped


    # dry run for test
    if dry_run:
        print("Dry run: do not push it back to device.")
        return CompressResult.Success

    original_mtime = os.path.getmtime(local_original)
    if adb_push(local_compressed, full_path, original_mtime) != 0:
        return CompressResult.Failure

    return CompressResult.Success


def need_to_compress(video_info: dict, quality: str) -> bool:
    """Check whether the video need to be compressed."""
    target_bitrate = get_target_bitrate(video_info, quality)
    if video_info['bitrate'] < target_bitrate * 1.2:
        return False
    return True


def compress_multiple_remote_video(full_paths, quality, dry_run: bool) -> int:
    """Compress multiple remote video files."""
    print(f"Compressing {len(full_paths)} video files with {quality} quality...\n")
    counters = {r:0 for r in CompressResult}
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, (full_path, size) in enumerate(full_paths.items()):
            print(f"Processing {i+1}/{len(full_paths)} file: {full_path}")
            if size < 1*MB:
                print(f"File size {size} is too small to be worth compressing, skipping.\n")
                counters[CompressResult.Skipped] += 1
                continue
            result = compress_remote_video(full_path, tmpdir, quality, dry_run)
            counters[result] += 1
            print() # Add a newline for better readability
    print(f"Compressed {counters[CompressResult.Success]}, "
          f"skipped {counters[CompressResult.Skipped]}, "
          f"failed {counters[CompressResult.Failure]} files.")
    return int(counters[CompressResult.Failure] != 0)


def scan_video_dir(device_path: str) -> dict:
    """Compress all video files in a remote directory."""
    cmd = ['adb', 'shell', rf'find {device_path} -type f -name "*.mp4" -printf "%s %p\n"']
    output = subprocess.check_output(cmd, text=True)
    return parse_find_output(output)


def parse_find_output(output: str) -> dict:
    """Parse the output of the find command."""
    result = {}
    for line in output.splitlines():
        #print(line)
        parts = line.split(" ", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid line: {line}")
        result[parts[1]] = int(parts[0])
    return result


def compress_video_file(device_path: str, quality: str, dry_run: bool) -> int:
    """Compress a single remote video file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        return compress_remote_video(device_path, tmpdir, quality, dry_run)


def compress_paths(device_paths: typing.List[str], quality: str, dry_run: bool) -> int:
    """Compress a video file or video files under directory on the Android device."""
    paths = {}
    nonexist_count = 0
    for device_path in device_paths:
        try:
            st = adb_stat(device_path)
        except Exception as e:
            print(f"Remote path {device_path} does not exist.  {e}")
            nonexist_count += 1
            continue
        if stat.S_ISDIR(st.st_mode):
            paths.update(scan_video_dir(device_path))
        else:
            paths.update({device_path: st.st_size})
    if not paths:
        print("No valid video files found to compress.")
        return int(nonexist_count != 0)
    return compress_multiple_remote_video(paths, quality, dry_run)


def adb_stat(path: str, device: str="") -> os.stat_result:
    """
    Get file stat info from an Android device via adb.
    Returns an os.stat_result object, same as os.stat().

    :param path: File path on the device
    :param device: Optional device serial (adb -s)
    :return: os.stat_result
    """
    # Build adb command
    cmd = ["adb"]
    if device:
        cmd += ["-s", device]
    stat_cmd = f'stat -c "%s %f %u %g %d %i %h %X %Y %Z" "{path}"'
    cmd += ["shell", stat_cmd]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = result.stdout.strip()
        if not output:
            raise FileNotFoundError(f"No such file: {path}")

        # Parse stat output
        size, mode_hex, uid, gid, dev, inode, nlink, atime, mtime, ctime = output.split()

        # Build os.stat_result (fields: mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime)
        stat_tuple = (
            int(mode_hex, 16),  # st_mode
            int(inode),         # st_ino
            int(dev),           # st_dev
            int(nlink),         # st_nlink
            int(uid),           # st_uid
            int(gid),           # st_gid
            int(size),          # st_size
            int(atime),         # st_atime
            int(mtime),         # st_mtime
            int(ctime)          # st_ctime
        )

        return os.stat_result(stat_tuple)

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ADB command failed: {e.stderr.strip()}")


def remote_path_exists(path: str, device: str = "") -> bool:
    """
    Check if a path exists on the Android device.
    :param path: Remote path on device
    :param device: Optional device ID
    :return: True if the path exists, False otherwise
    """
    adb_cmd = ["adb"]
    if device:
        adb_cmd += ["-s", device]
    adb_cmd += ["shell", f'test -e "{path}" && echo exists || echo not_exist']

    result = subprocess.run(adb_cmd, capture_output=True, text=True, check=False)
    return "exists" in result.stdout


def remote_path_isdir(path: str, device: str = "") -> bool:
    """
    Check if a path on the Android device is a directory.
    :param path: Remote path on device
    :param device: Optional device ID
    :return: True if it is a directory, False otherwise
    """
    adb_cmd = ["adb"]
    if device:
        adb_cmd += ["-s", device]
    adb_cmd += ["shell", f'test -d "{path}" && echo dir || echo file']

    result = subprocess.run(adb_cmd, capture_output=True, text=True, check=False)
    return "dir" in result.stdout


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="video/compress.py",
        usage = "Compress video files on Android device to reduce the storage.",
        description=textwrap.dedent("""
            Each path can be a single video file or a directory containing video files.
            The program will use the best available encoder according to your system.
            The compressed video will be pushed back to the device with the original timestamp.

            Example usage:
              python video/compress.py -q medium /sdcard/Movies/video.mp4
              python video/compress.py -q high /sdcard/Movies
              python video/compress.py /sdcard/DCIM/Camera /sdcard/Movies
        """),
        epilog=textwrap.dedent("""
            Note: This script requires adb, ffmpeg and exiftool to be installed on your system.
            Make sure you have adb set up and connected to your Android device.
        """),
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "-q", "--quality",
        choices=QUALITY_CHOICES,
        default="medium",
        help="Compression quality (high, medium, low)"
    )
    parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Perform a dry run without actually pushing files"
    )

    parser.add_argument(
        "video_paths",
        nargs="+",
        help="Input video file(s)"
    )
    return parser.parse_args()


def main():
    """Main function to compress video files."""
    args = parse_args()

    encoder = get_best_encoder()
    if encoder == 'libx265':
        print("Warning: Hardware encoder is unavailable, compression may be slow.")

    if subprocess.call(['adb', 'shell', 'pwd'], stdout=subprocess.DEVNULL) != 0:
        print("ADB is not connected or not working properly.")
        return 1

    return compress_paths(args.video_paths, quality=args.quality, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
