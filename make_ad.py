#!/usr/bin/env python3
"""Create a vertical UGC-style ad from user-supplied clips and an AI voice-over."""
import argparse
import asyncio
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm"}

def run(cmd):
    print("+", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True)

def clean(s):
    return re.sub(r"\s+", " ", s).strip()

def build_script(product, audience, problem, benefit, offer, cta, seconds):
    # Keep wording grounded in the user-provided facts; do not invent testimonials/results.
    lines = [
        f"Quick tip if you're {audience}.",
        f"If {problem} has been bothering you, here's something to consider: {product}.",
        f"It's designed to help with {benefit}.",
    ]
    if offer:
        lines.append(f"Here's the offer: {offer}.")
    lines.append(f"If it sounds right for you, {cta}.")
    text = " ".join(clean(x) for x in lines)
    # Trim long copy to a practical short-form read.
    words = text.split()
    max_words = max(45, int(seconds * 2.25))
    if len(words) > max_words:
        text = " ".join(words[:max_words]).rstrip(" ,;:") + "."
    return text

async def make_voice(text, output, voice):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output))

def srt_time(seconds):
    ms = int(seconds * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def make_srt(text, duration, path):
    words = text.split()
    # Caption chunks of up to 6 words, distributed over the voice duration.
    chunks = [" ".join(words[i:i+6]) for i in range(0, len(words), 6)]
    per = duration / max(1, len(chunks))
    with path.open("w", encoding="utf-8") as f:
        for i, chunk in enumerate(chunks, 1):
            start = i * per - per
            end = min(duration, (i * per) - 0.05)
            f.write(f"{i}\n{srt_time(start)} --> {srt_time(max(start+0.25,end))}\n{chunk}\n\n")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--product", required=True)
    p.add_argument("--audience", required=True)
    p.add_argument("--problem", required=True)
    p.add_argument("--benefit", required=True)
    p.add_argument("--offer", default="")
    p.add_argument("--cta", default="tap the link to learn more")
    p.add_argument("--voice", default="en-US-JennyNeural")
    p.add_argument("--seconds", type=int, default=25)
    args = p.parse_args()

    assets = Path("assets")
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    clips = sorted(x for x in assets.glob("*") if x.suffix.lower() in VIDEO_EXTS)
    if not clips:
        sys.exit("No video clips found. Upload at least one clip to assets/ (MP4, MOV, M4V, or WEBM).")
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        sys.exit("FFmpeg and ffprobe are required.")

    script = build_script(args.product, args.audience, args.problem, args.benefit, args.offer, args.cta, args.seconds)
    (output_dir / "ad-script.txt").write_text(script, encoding="utf-8")
    voice_file = output_dir / "voice.mp3"
    asyncio.run(make_voice(script, voice_file, args.voice))

    # Normalize each clip to a common vertical format, mute original audio, and trim each to 6 seconds.
    normalized = []
    for i, clip in enumerate(clips[:5]):
        target = output_dir / f"segment_{i:02}.mp4"
        run(["ffmpeg", "-y", "-i", str(clip), "-t", "6",
             "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1",
             "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
             str(target)])
        normalized.append(target)

    concat_file = output_dir / "concat.txt"
    concat_file.write_text("".join(f"file '{x.resolve().as_posix()}'\n" for x in normalized), encoding="utf-8")
    silent_video = output_dir / "silent.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(silent_video)])

    probe = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                      "-of", "default=noprint_wrappers=1:nokey=1", str(voice_file)], text=True)
    voice_duration = float(probe.strip())
    video_duration = min(max(voice_duration + 1, 8), sum(6 for _ in normalized))
    srt = output_dir / "captions.srt"
    make_srt(script, min(voice_duration, video_duration), srt)

    # Loop footage if the narration is longer than the selected clips; stop at narration end.
    final = output_dir / "dominion-empire-ugc-ad.mp4"
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(silent_video), "-i", str(voice_file),
         "-t", f"{voice_duration:.2f}",
         "-vf", f"subtitles={srt.as_posix()}:force_style='FontName=Arial,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=190'",
         "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
         "-c:a", "aac", "-b:a", "192k", "-shortest", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(final)])
    print(f"\nDONE: {final}")
    print("\nAD SCRIPT:\n" + script)

if __name__ == "__main__":
    main()
