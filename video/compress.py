#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Compress video files on Android device using ffmpeg.
This script will compress the video files on the Android device using ffmpeg.
It will use the best available encoder according to the system and ffmpeg configuration.
The compressed video will be pushed back to the device with the original timestamp.
"""

import argparse
import subprocess
import os
import sys
import tempfile
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


def get_encoder_quality(encoder: str, quality: str) -> list[str]:
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


def check_encoders(encoders: list[str], default: str='libx265') -> str:
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


def adb_push_with_timestamp(local_path: str, device_path: str, timestamp: float):
    """Push a file to the Android device and set its timestamp."""
    print("Pushing back compressed file to device.")
    returncode = subprocess.call(["adb", "push", local_path, device_path])
    if returncode != 0:
        return returncode

    dt = datetime.fromtimestamp(timestamp)
    touch_time = dt.strftime("%Y%m%d%H%M.%S")

    cmd = f"touch -t {touch_time} {device_path}"
    return subprocess.call(["adb", "shell", cmd], stdout=subprocess.DEVNULL)


def is_compressed(compressed_size: int, original_size: int) -> bool:
    """Check whether the video is effectively compressed."""
    if compressed_size >= original_size:
        print(f"Compressed size is larger: {compressed_size} > {original_size}.")
        return False
    if compressed_size / original_size > 0.9:
        print(f"Compressed size is not smaller enough: {compressed_size} vs {original_size}.")
        return False
    return True


def compress_remote_video(full_path: str, tmpdir: str, quality: str, dry_run: bool) -> int:
    """Compress a remote video file."""
    local_original = os.path.join(tmpdir, "original.mp4")
    local_compressed = os.path.join(tmpdir, "compressed.mp4")

    print(f"Processing file: {full_path}")

    if adb_pull_file(full_path, local_original) != 0:
        return 1

    video_info = get_video_info(local_original)

    if not need_to_compress(video_info, quality):
        print('File is already compressed at the expected format.')
        return 0

    print("Compressing file...")
    if compress_video_ffmpeg(local_original, local_compressed, quality) != 0:
        return 1

    compressed_size = os.path.getsize(local_compressed)
    original_size = os.path.getsize(local_original)
    if not is_compressed(compressed_size, original_size):
        print("Compressed file is not smaller than original, skipping push.")
        return 0

    print(f"Compress rate: {compressed_size}/{original_size} = {compressed_size / original_size:.2%}")

    # dry run for test
    if dry_run:
        print("Dry run: Skipped to push it back to device.")
        return 0

    original_mtime = os.path.getmtime(local_original)
    return adb_push_with_timestamp(local_compressed, full_path, original_mtime)


def need_to_compress(video_info: dict, quality: str) -> bool:
    """Check whether the video need to be compressed."""
    target_bitrate = get_target_bitrate(video_info, quality)
    if video_info['bitrate'] < target_bitrate * 1.1:
        return False
    return True


def compress_multiple_remote_video(full_paths, quality, dry_run: bool) -> int:
    """Compress multiple remote video files."""
    print(f"Compressing {len(full_paths)} video files with {quality} quality ...\n")
    success_count = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        for full_path, size in full_paths.items():
            if size > 0 and size < 1*MB:
                print(f"File{full_path} is too small to be worth compressing, skipping.")
                success_count += 1
                continue
            success_count += compress_remote_video(full_path, tmpdir, quality, dry_run)
            print() # Add a newline for better readability
    print(f"Compressed {success_count} out of {len(full_paths)} video files.")
    return 0 if success_count == len(full_paths) else 1


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
    for device_path in device_paths:
        if not remote_path_exists(device_path):
            print(f"Remote path {device_path} does not exist.")
            continue
        if remote_path_isdir(device_path):
            paths.update(scan_video_dir(device_path))
        else:
            paths.update({device_path: 0})  # Size will be determined later
    if not paths:
        print("No valid video files found to compress.")
        return 0
    return compress_multiple_remote_video(paths, quality, dry_run)


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
        description="Video compression script with quality options"
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
