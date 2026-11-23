#!/usr/bin/env python3
"""Create a scene-matched vertical ad using OpenAI vision + Edge TTS.

OpenAI receives timestamped still frames sampled throughout each supplied clip.
It returns a scene plan; FFmpeg then cuts the relevant source ranges and aligns
one spoken narration segment with each visual segment.
"""
import argparse
import asyncio
import base64
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from openai import OpenAI

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm"}
MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")


def run(cmd):
    print("+", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True)


def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def probe_duration(path):
    result = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ], text=True)
    return max(0.0, float(result.strip()))


def srt_time(seconds):
    ms = int(seconds * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def sample_frames(clips, work_dir, max_frames=30):
    """Sample frames across every clip; return labelled image paths and durations."""
    samples, durations = [], []
    per_clip = max(1, max_frames // len(clips))
    for clip_index, clip in enumerate(clips):
        duration = probe_duration(clip)
        durations.append(duration)
        if duration <= 0:
            continue
        count = min(per_clip, max(1, int(duration // 2) + 1))
        times = [min(duration - 0.15, (i + 0.5) * duration / count) for i in range(count)]
        for frame_index, timestamp in enumerate(times):
            frame = work_dir / f"frame_c{clip_index:02}_f{frame_index:02}.jpg"
            run(["ffmpeg", "-y", "-ss", f"{timestamp:.3f}", "-i", str(clip),
                 "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "5", str(frame)])
            if frame.exists() and frame.stat().st_size:
                samples.append({
                    "clip_index": clip_index,
                    "clip_name": clip.name,
                    "timestamp": round(timestamp, 2),
                    "path": frame,
                })
    if not samples:
        raise RuntimeError("Could not extract any frames from the supplied videos.")
    return samples, durations


def analyse_and_plan(clips, samples, durations, args):
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is missing. Add it in GitHub Settings > Secrets and variables > Actions.")
    client = OpenAI()
    content = [{
        "type": "input_text",
        "text": (
            "You are an experienced direct-response video editor. Inspect EVERY supplied timestamped frame. "
            "The frames are sampled from the user's own source clips. Build a truthful, coherent short ad. "
            "Do not invent product features, ingredients, results, testimonials, prices, or claims. "
            "Use only the product facts supplied below. Match each spoken sentence to footage that visibly "
            "supports it. If no footage visibly supports a claim, use a neutral relevant shot and keep the "
            "claim cautious. Use source clip indices and timestamps only from the supplied frames. "
            "Return valid JSON only, with this shape: "
            '{"scenes":[{"clip_index":0,"start_sec":0.0,"end_sec":3.0,'
            '"narration":"One complete spoken sentence.","on_screen_text":"Short readable phrase",'
            '"visual_reason":"Why this footage matches the narration"}]}. '
            "Create enough scenes for the requested duration. Each scene should normally be 2–6 seconds. "
            "The start/end times must stay within the duration of the selected clip. Keep the full script "
            "natural, specific, persuasive but not exaggerated. Avoid a generic opening hook unrelated to "
            "the footage. On-screen text should summarize the current spoken sentence, not repeat a hook. "
            f"Requested target length: {args.seconds} seconds.\n"
            f"Product: {args.product}\nAudience: {args.audience}\nProblem: {args.problem}\n"
            f"Verified benefit supplied by user: {args.benefit}\nOffer: {args.offer or 'None'}\n"
            f"Call to action: {args.cta}\n"
            "Available source clips and durations (seconds): "
            + json.dumps([{"clip_index": i, "name": c.name, "duration": round(d, 2)}
                          for i, (c, d) in enumerate(zip(clips, durations))])
            + "\nFrames follow. Each frame is labelled with its clip index and timestamp."
        )
    }]
    for item in samples:
        content.append({
            "type": "input_text",
            "text": f"FRAME: clip_index={item['clip_index']}, timestamp_seconds={item['timestamp']}, file={item['clip_name']}"
        })
        encoded = base64.b64encode(item["path"].read_bytes()).decode("ascii")
        content.append({
            "type": "input_image",
            "image_url": f"data:image/jpeg;base64,{encoded}",
            "detail": "low",
        })
    response = client.responses.create(
        model=MODEL,
        input=[{"role": "user", "content": content}],
        text={"format": {"type": "json_object"}},
        max_output_tokens=3000,
    )
    try:
        plan = json.loads(response.output_text)
    except Exception as exc:
        raise RuntimeError(f"OpenAI returned a response that was not valid JSON: {response.output_text[:800]}") from exc
    scenes = plan.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise RuntimeError("OpenAI did not return any usable scenes.")
    valid = []
    for scene in scenes:
        try:
            ci = int(scene["clip_index"])
            start = max(0.0, float(scene["start_sec"]))
            end = min(durations[ci], float(scene["end_sec"]))
            narration = clean(scene["narration"])
            overlay = clean(scene.get("on_screen_text", ""))
            reason = clean(scene.get("visual_reason", ""))
            if ci < 0 or ci >= len(clips) or end <= start or not narration:
                continue
            valid.append({
                "clip_index": ci, "start_sec": round(start, 2), "end_sec": round(end, 2),
                "narration": narration, "on_screen_text": overlay[:90],
                "visual_reason": reason[:240],
            })
        except (KeyError, TypeError, ValueError, IndexError):
            continue
    if not valid:
        raise RuntimeError("The AI scene plan contained no valid clip ranges.")
    return {"model": MODEL, "scenes": valid}


async def make_voice(text, output, voice):
    import edge_tts
    await edge_tts.Communicate(text, voice).save(str(output))


def make_srt(scenes, durations, path):
    elapsed = 0.0
    entries = []
    for i, (scene, duration) in enumerate(zip(scenes, durations), 1):
        caption = scene["on_screen_text"] or scene["narration"]
        entries.append(f"{i}\n{srt_time(elapsed)} --> {srt_time(elapsed + duration)}\n{caption}\n")
        elapsed += duration
    path.write_text("\n".join(entries), encoding="utf-8")


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
    work_dir = output_dir / "analysis_frames"
    output_dir.mkdir(exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    clips = sorted(x for x in assets.glob("*") if x.suffix.lower() in VIDEO_EXTS)
    if not clips:
        sys.exit("No video clips found. Upload at least one clip to assets/.")
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        sys.exit("FFmpeg and ffprobe are required.")
    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is missing from GitHub Actions secrets.")

    print(f"Sampling frames from {len(clips)} source clip(s)...")
    samples, durations = sample_frames(clips, work_dir)
    print(f"Sending {len(samples)} timestamped frames to {MODEL} for scene analysis...")
    plan = analyse_and_plan(clips, samples, durations, args)
    (output_dir / "ad-storyboard.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")

    voice_files, voice_durations, used_scenes = [], [], []
    for index, scene in enumerate(plan["scenes"]):
        voice_file = output_dir / f"voice_scene_{index:02}.mp3"
        asyncio.run(make_voice(scene["narration"], voice_file, args.voice))
        duration = probe_duration(voice_file)
        if duration <= 0:
            continue
        voice_files.append(voice_file)
        voice_durations.append(duration)
        used_scenes.append(scene)

    if not voice_files:
        raise RuntimeError("Voice generation did not produce any audio.")

    segment_files = []
    for index, (scene, voice_duration) in enumerate(zip(used_scenes, voice_durations)):
        clip = clips[scene["clip_index"]]
        segment = output_dir / f"visual_scene_{index:02}.mp4"
        run([
            "ffmpeg", "-y", "-stream_loop", "-1", "-ss", f"{scene['start_sec']:.2f}",
            "-i", str(clip), "-t", f"{voice_duration:.3f}",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1",
            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-pix_fmt", "yuv420p", str(segment)
        ])
        segment_files.append(segment)

    visual_list = output_dir / "visual_concat.txt"
    visual_list.write_text("".join(f"file '{x.resolve().as_posix()}'\n" for x in segment_files), encoding="utf-8")
    voice_list = output_dir / "voice_concat.txt"
    voice_list.write_text("".join(f"file '{x.resolve().as_posix()}'\n" for x in voice_files), encoding="utf-8")
    silent_video = output_dir / "silent.mp4"
    joined_voice = output_dir / "joined_voice.mp3"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(visual_list), "-c", "copy", str(silent_video)])
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(voice_list), "-c:a", "libmp3lame", "-q:a", "3", str(joined_voice)])

    srt = output_dir / "captions.srt"
    make_srt(used_scenes, voice_durations, srt)
    final = output_dir / "dominion-empire-ugc-ad.mp4"
    run([
        "ffmpeg", "-y", "-i", str(silent_video), "-i", str(joined_voice),
        "-vf", f"subtitles={srt.as_posix()}:force_style='FontName=Arial,FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=190'",
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "22", "-c:a", "aac", "-b:a", "192k", "-shortest",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(final)
    ])

    full_script = "\n".join(scene["narration"] for scene in used_scenes)
    (output_dir / "ad-script.txt").write_text(full_script, encoding="utf-8")
    print(f"\nDONE: {final}")
    print("\nSCENE-BY-SCENE SCRIPT:\n" + full_script)


if __name__ == "__main__":
    main()
