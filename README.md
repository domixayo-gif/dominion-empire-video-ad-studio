# Dominion Empire — UGC Video Ad Studio

Create vertical UGC-style MP4 ads with an AI voice-over using GitHub Actions.

## What it does
- Takes your own product/lifestyle video clips from `assets/`
- Writes a short ad script from the product details you enter
- Generates an AI voice-over with Microsoft Edge TTS
- Crops/combines footage into a 9:16 video, adds readable captions and exports an MP4
- Uploads the finished MP4 as a downloadable GitHub Actions artifact

**Important:** This first version edits footage you provide. It does not generate a synthetic human/avatar or fetch stock footage automatically. Use footage you own or have permission to use, and make truthful product claims.

## 1. Add your footage
Upload 1–5 vertical or horizontal product/demo/lifestyle clips into `assets/` (MP4, MOV, or WEBM). Keep each clip reasonably short (5–30 seconds). Example:
```
assets/
  clip1.mp4
  clip2.mp4
``

## 2. Generate an ad
1. Open the **Actions** tab.
2. Select **Create UGC Video Ad**.
3. Click **Run workflow**.
4. Enter product name, target audience, problem, benefit, offer (optional), and call to action.
5. Choose a voice and duration, then run it.

When complete, open the successful workflow run and download **dominion-empire-video-ad** under Artifacts. Extract the ZIP to get your MP4.

## Voice options
The workflow uses Edge TTS neural voices (internet access required). Default: Nigerian English is not guaranteed; select an English voice from the workflow list.

## Local run (optional)
Requires Python 3.11, FFmpeg, and internet access:
```bash
pip install -r requirements.txt
python make_ad.py --product "Vitamin C Serum" --audience "women who want a brighter-looking skincare routine" --problem "dull-looking skin" --benefit "a simple serum step for your routine" --cta "Learn more"
```

Place clips in `assets/`. Output is written to `output/dominion-empire-ugc-ad.mp4`.

## Notes
- AI voice is generated speech, not a real customer testimonial. Do not present scripted copy as a genuine customer review.
- Add product footage, packaging, demonstrations, and real licensed UGC. Avoid unsupported before/after or medical claims.
- GitHub Actions artifacts are temporary (retention is set to 7 days); download your MP4 after the run.
