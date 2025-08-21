import subprocess
import sys
import json

def get_video_info(file_path):
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams", "-show_format",
        file_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, check=True)
    info = json.loads(result.stdout)

    # Find the first video stream
    video_stream = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    if not video_stream:
        return None

    duration = float(info["format"]["duration"])
    width = int(video_stream["width"])
    height = int(video_stream["height"])
    bitrate = int(info["format"]["bit_rate"])

    r_frame_rate = video_stream.get("r_frame_rate", "0/1")
    num, den = map(int, r_frame_rate.split("/"))
    fps = num / den if den != 0 else 0

    codec_name = video_stream.get("codec_name", "unknown")

    return {
        "duration": duration,
        "width": width,
        "height": height,
        "bitrate": bitrate,
        "fps": fps,
        "codec": codec_name
    }


def main():
    for file in sys.argv[1:]:
        video_info = get_video_info(file)
        if video_info:
            print(f"path: {file}")
            print(f"codec: {video_info['codec']}")
            print(f"duration: {video_info['duration']:.2f} 秒")
            print(f"resultion: {video_info['width']}x{video_info['height']}")
            print(f"bitrate: {video_info['bitrate'] / 1000:.2f} kbps")
            print(f"FPS: {video_info['fps']:.2f}")


if __name__ == '__main__':
    main()
