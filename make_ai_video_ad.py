#!/usr/bin/env python3
"""Generate a complete vertical ad from text prompts using Runway text-to-video."""
import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import requests
from openai import OpenAI
from runwayml import RunwayML, TaskFailedError

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
RUNWAY_MODEL = os.getenv("RUNWAY_VIDEO_MODEL", "seedance2_5")
RUNWAY_VERSION = "2024-11-06"


def run(command):
    print("+", " ".join(map(str, command)), flush=True)
    subprocess.run(command, check=True)


def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def probe_duration(path):
    value = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ], text=True)
    return float(value.strip())


def timestamp(seconds):
    total_ms = int(seconds * 1000)
    hours, total_ms = divmod(total_ms, 3600000)
    minutes, total_ms = divmod(total_ms, 60000)
    secs, millis = divmod(total_ms, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def create_scene_plan(args):
    client = OpenAI()
    scene_count = max(3, min(7, round(args.seconds / 5)))
    prompt = f"""
You are a senior direct-response creative director making a truthful social video ad.
Create exactly {scene_count} connected scenes for a {args.seconds}-second vertical 9:16 ad.
Each scene will become a REAL MOVING VIDEO generated from its visual_prompt.
Do not describe still images, slideshows, camera zooms on photos, or static posters.
Describe visible physical action, camera movement, setting, lighting, and subject movement.
Keep the same main person and visual style consistent across scenes where practical.
The scene must visibly match its narration. If narration mentions applying a product,
show the action of applying it. If it mentions the product, show a relevant product interaction.
Never invent clinical results, ingredients, certifications, testimonials, prices, or guarantees.
Do not claim a person is a real customer. Do not put readable text or logos inside the generated footage;
captions and product wording will be added during editing.
Keep each narration short enough for about five seconds of natural speech (roughly 7–11 words).
Return JSON only in this exact shape:
{{"scenes":[{{"narration":"One short spoken line.","visual_prompt":"Detailed prompt for a moving 5-second video shot.","on_screen_text":"Short matching phrase.","visual_reason":"How the moving action supports the spoken line."}}]}}
Product: {args.product}
Target audience: {args.audience}
Audience problem: {args.problem}
Verified benefit supplied by user: {args.benefit}
Offer: {args.offer or "No offer supplied"}
Call to action: {args.cta}
Voice style: natural, friendly, confident UGC-style commercial.
Structure: hook, relatable problem, product/routine demonstration, supported benefit, CTA.
"""
    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt,
        text={"format": {"type": "json_object"}},
        max_output_tokens=3500,
    )
    data = json.loads(response.output_text)
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or len(scenes) != scene_count:
        raise RuntimeError(f"AI must return exactly {scene_count} scenes.")
    valid = []
    for scene in scenes:
        narration = clean(scene.get("narration"))
        visual_prompt = clean(scene.get("visual_prompt"))
        if not narration or not visual_prompt:
            raise RuntimeError("A scene is missing narration or a moving-video prompt.")
        valid.append({
            "narration": narration,
            "visual_prompt": visual_prompt,
            "on_screen_text": clean(scene.get("on_screen_text"))[:80],
            "visual_reason": clean(scene.get("visual_reason"))[:240],
        })
    return {"openai_model": OPENAI_MODEL, "video_model": RUNWAY_MODEL, "scenes": valid}


async def make_voice(text, path, voice):
    import edge_tts
    await edge_tts.Communicate(text, voice).save(str(path))


def generate_video(client, prompt, output_path):
    try:
        task = client.text_to_video.create(
            model=RUNWAY_MODEL,
            prompt_text=prompt + " Natural realistic motion, coherent anatomy, commercial cinematography.",
            ratio="720:1280",
            duration=5,
            audio=False,
        ).wait_for_task_output()
    except TaskFailedError as exc:
        raise RuntimeError(f"Runway video generation failed: {exc.task_details}") from exc

    outputs = getattr(task, "output", None)
    if not outputs and isinstance(task, dict):
        outputs = task.get("output")
    if not outputs:
        raise RuntimeError(f"Runway returned no video output: {task}")
    video_url = outputs[0]
    response = requests.get(video_url, timeout=180)
    response.raise_for_status()
    output_path.write_bytes(response.content)
    if output_path.stat().st_size < 10000:
        raise RuntimeError("The generated video file is unexpectedly small.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", required=True)
    parser.add_argument("--audience", required=True)
    parser.add_argument("--problem", required=True)
    parser.add_argument("--benefit", required=True)
    parser.add_argument("--offer", default="")
    parser.add_argument("--cta", default="Tap the link to learn more")
    parser.add_argument("--voice", default="en-US-JennyNeural")
    parser.add_argument("--seconds", type=int, choices=[15, 25, 35], default=25)
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is missing from GitHub Actions secrets.")
    if not os.getenv("RUNWAYML_API_SECRET"):
        sys.exit("RUNWAYML_API_SECRET is missing. Add it as a GitHub Actions secret.")
    for binary in ("ffmpeg", "ffprobe"):
        if subprocess.call(["bash", "-lc", f"command -v {binary} >/dev/null 2>&1"]) != 0:
            sys.exit(f"{binary} is required.")

    output = Path("output")
    output.mkdir(exist_ok=True)
    print("Planning the ad scene by scene...")
    plan = create_scene_plan(args)
    (output / "ad-storyboard.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")

    # Generate and validate ALL narration before making any billable video requests.
    video_files, voice_files, voice_durations, used_scenes = [], [], [], []
    for index, scene in enumerate(plan["scenes"]):
        voice_path = output / f"voice_scene_{index:02}.mp3"
        asyncio.run(make_voice(scene["narration"], voice_path, args.voice))
        voice_duration = probe_duration(voice_path)
        if voice_duration > 5.0:
            raise RuntimeError(
                f"Scene {index + 1} voice-over is {voice_duration:.1f}s, longer than its 5s video. "
                "The narration was too long; shorten the scene line and run again. No video generation has started."
            )
        voice_files.append(voice_path)
        voice_durations.append(voice_duration)
        used_scenes.append(scene)

    runway = RunwayML()
    for index, scene in enumerate(used_scenes):
        print(f"Generating moving video scene {index + 1}/{len(used_scenes)}...")
        video_path = output / f"ai_scene_{index:02}.mp4"
        generate_video(runway, scene["visual_prompt"], video_path)
        video_files.append(video_path)

    segments = []
    for index, (video_path, voice_duration) in enumerate(zip(video_files, voice_durations)):
        segment = output / f"render_scene_{index:02}.mp4"
        run([
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(video_path),
            "-t", f"{voice_duration:.3f}",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1",
            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-pix_fmt", "yuv420p", str(segment)
        ])
        segments.append(segment)

    video_list = output / "video_concat.txt"
    video_list.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in segments), encoding="utf-8")
    voice_list = output / "voice_concat.txt"
    voice_list.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in voice_files), encoding="utf-8")
    silent = output / "silent.mp4"
    joined_voice = output / "joined_voice.mp3"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(video_list), "-c", "copy", str(silent)])
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(voice_list), "-c:a", "libmp3lame", "-q:a", "3", str(joined_voice)])

    elapsed, captions = 0.0, []
    for index, (scene, duration) in enumerate(zip(used_scenes, voice_durations), 1):
        caption = scene["on_screen_text"] or scene["narration"]
        captions.append(f"{index}\n{timestamp(elapsed)} --> {timestamp(elapsed + duration)}\n{caption}\n")
        elapsed += duration
    srt = output / "captions.srt"
    srt.write_text("\n".join(captions), encoding="utf-8")

    final = output / "dominion-empire-ai-video-ad.mp4"
    run([
        "ffmpeg", "-y", "-i", str(silent), "-i", str(joined_voice),
        "-vf", f"subtitles={srt.as_posix()}:force_style='FontName=Arial,FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=190'",
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "22", "-c:a", "aac", "-b:a", "192k", "-shortest",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(final)
    ])
    (output / "ad-script.txt").write_text("\n".join(s["narration"] for s in used_scenes), encoding="utf-8")
    print(f"COMPLETE: {final}", flush=True)


if __name__ == "__main__":
    main()
