#!/usr/bin/env python3
import subprocess
import os
import sys
import tempfile
from datetime import datetime

from info import get_video_info


MB = 1024*1024


def adb_pull_file(device_path: str, local_path: str) -> int:
    print(f"Pulling file from device: {device_path} -> {local_path}")
    # The `-a` option make the file time synced
    return subprocess.call(["adb", "pull", "-a", device_path, local_path])


encoder_args = {
    "hevc_videotoolbox": [],
    "hevc_nvenc": [],
    "hevc_qsv": [],
    "hevc_amf": [],
    "libx265": []
}


def compress_video_ffmpeg(input_path: str, output_path: str, video_info: dict) -> int:
    print(f"Compressing video: {input_path} -> {output_path}")

    encoder = get_best_encoder()
    bitrate = get_target_bitrate(video_info)

    cmd = [
        "ffmpeg",
        "-y", "-v", "error", "-stats",
        "-i", input_path,
        "-c:v", encoder,
        "-pix_fmt", "yuv420p",
        "-profile:v", "main",
        "-tag:v", "hvc1",
        "-b:v", str(bitrate),
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        "-map", "0", # Keep somthing like subtitle
        "-map_metadata", "0",   # Copy all metadata
        output_path
    ]
    returncode = subprocess.call(cmd)
    if returncode != 0:
        return returncode
    # Copy all exif infomation.
    cmd = ["exiftool", "-tagsFromFile", input_path, "-all:all", "-unsafe", output_path]
    return subprocess.call(cmd)


BEST_ENCODER = None

def get_best_encoder() -> str:
    """Get the best vodeo encoder according the system and ffmpeg configuration."""
    global BEST_ENCODER
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
            print(f"Find h265 encoder: {encoder}")
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


def get_target_bitrate(video_info) -> int:
    # For a 1920x1080, 30FPS, HEVC (H.265) video, the suitable bitrate depends on the purpose and quality requirements:
    #
    # Purpose / Quality          Recommended Bitrate (HEVC)   Notes
    # ----------------------------------------------------------------------
    # High Quality (near-lossless)  15–20 Mbps                For archiving, re-editing, or professional use
    # Premium Playback               8–12 Mbps                Blu-ray like quality, minimal visible compression
    # Standard Web Upload            4–6 Mbps                 Common range for YouTube, Bilibili
    # Maximum Compression            2–3 Mbps                 Suitable for low-bandwidth delivery, but some detail loss
    area = video_info["width"] * video_info["height"]
    # For a H265 encoded video wtih 1920*1080 30FPS, the blueray is about 5M
    return int(area * 2.5)


def adb_push_with_timestamp(local_path: str, device_path: str, timestamp: float):
    print(f"Pushing compressed file back to device: {local_path} -> {device_path}")
    returncode = subprocess.call(["adb", "push", local_path, device_path])
    if returncode != 0:
        return returncode

    dt = datetime.fromtimestamp(timestamp)
    touch_time = dt.strftime("%Y%m%d%H%M.%S")

    cmd = f"touch -t {touch_time} {device_path}"
    result = subprocess.run(["adb", "shell", cmd], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print(f"adb shell touch failed: {result.stderr}")
    else:
        print(f"Timestamp set to {touch_time} on device file")
    return result.returncode


def is_compressed(compressed: str, origin: str) -> bool:
    """Check whether the video is effectively compressed."""
    compressed_size = os.path.getsize(compressed)
    original_size = os.path.getsize(origin)
    if compressed_size >= original_size:
        print(f"Compressed file size {compressed_size} is not smaller than original size {original_size}.")
        return False
    if compressed_size / original_size > 0.9:
        print(f"Compressed file size {compressed_size} is not significantly smaller than original size {original_size}.")
        return False
    print(f"Compress rate: {compressed_size / original_size:.2%}")
    return True


def compress_remote_video(full_path: str, tmpdir) -> bool:
    local_original = os.path.join(tmpdir, "original.mp4")
    local_compressed = os.path.join(tmpdir, "compressed.mp4")

    if adb_pull_file(full_path, local_original) != 0:
        return 1

    video_info = get_video_info(local_original)

    if not need_to_compress(video_info):
        print(f'Video {full_path} is already compressed at the expected format.')
        return True

    if compress_video_ffmpeg(local_original, local_compressed, video_info) != 0:
        return 1

    if not is_compressed(local_compressed, local_original):
        print("Compressed file is not smaller than original, skipping push.")
        return 0

    # dry run for test
    return 0

    original_mtime = os.path.getmtime(local_original)
    return adb_push_with_timestamp(local_compressed, device_path, original_mtime)


def need_to_compress(video_info: dict) -> bool:
    """Check whether the video need to be compressed."""
    target_bitrate = get_target_bitrate(video_info)
    if video_info['bitrate'] < target_bitrate * 1.1:
        return False
    return True


def compress_multiple_remote_video(full_paths) -> bool:
    with tempfile.TemporaryDirectory() as tmpdir:
        for full_path, size in full_paths.items():
            if size < 1*MB:
                print(f"Video {full_path} is too samll to compress, skip")
                continue
            compress_remote_video(full_path, tmpdir)
    return True


def compress_video_dir(device_path: str) -> int:
    cmd = ['adb', 'shell', rf'find {device_path} -type f -name "*.mp4" -printf "%s %p\n"']
    output = subprocess.check_output(cmd, text=True)
    video_files = parse_find_output(output)
    compress_multiple_remote_video(video_files)


def parse_find_output(output: str) -> dict:
    result = {}
    for line in output.splitlines():
        #print(line)
        parts = line.split(" ", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid line: {line}")
        result[parts[1]] = int(parts[0])
    return result


def compress_video_file(device_path: str) -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        return compress_remote_video(device_path, tmpdir)


def main():
    if len(sys.argv) != 2:
        print(f"Compress video on your android device.")
        print(f"Usage:")
        print(f"  {sys.argv[0]} [/path/on/device/video.mp4]")
        print(f"  {sys.argv[0]} [/path/on/device/dir/]")
        return 1

    encoder = get_best_encoder()
    if encoder == 'libx265':
        print(f"Can't use hardware encoder, compression may be slow.")

    device_path = sys.argv[1]
    if device_path.endswith('/'):
        return compress_video_dir(device_path)
    compress_video_file(device_path)


if __name__ == "__main__":
    sys.exit(main())