# Dominion Empire — AI Scene-by-Scene Video Ad Studio

Create vertical MP4 product ads from your own footage. OpenAI vision analyses timestamped frames sampled throughout every uploaded clip, writes a scene plan, and matches each narration segment to a relevant source range. Edge TTS generates the voice-over and FFmpeg renders the finished video.

## What it does
- Samples frames across all source clips and sends them to an OpenAI vision model for analysis
- Builds a scene-by-scene script and storyboard using the product facts you provide
- Generates a separate voice-over segment for each scene
- Uses the selected source clip and timestamp for each matching scene
- Adds scene-specific on-screen text and renders a vertical 9:16 MP4
- Uploads the MP4, script, and storyboard as a downloadable GitHub Actions artifact

**Important:** The model analyses timestamped still frames, not the original video as a continuous video input. It can miss fast actions or details between sampled frames. Review the storyboard and final video before publishing. It must not invent product claims, results, testimonials, ingredients, or offers.

## 1. Add your API key
In this repository, open **Settings → Secrets and variables → Actions → New repository secret**.
- Name: `OPENAI_API_KEY`
- Secret: your OpenAI API key

Never put the key in source code, commit it, or share it in an issue. The workflow reads it securely from GitHub Actions Secrets.

## 2. Add your footage
Upload 1–5 clips to `assets/` (MP4, MOV, M4V, or WEBM). Use footage you own or have permission to use. Keep clips reasonably short and clear.

**Repository visibility:** This repository is public. Files committed to `assets/` can be viewed by anyone. Do not upload private customer footage, confidential brand material, or personal videos unless you first make the repository private.

## 3. Generate an ad
1. Open the **Actions** tab.
2. Select **Create UGC Video Ad**.
3. Click **Run workflow**.
4. Enter the product, target audience, problem, truthful benefit, offer, and CTA.
5. Choose a voice and target length, then run it.

When complete, open the workflow run and download **dominion-empire-video-ad** under Artifacts. Extract the ZIP to get the MP4, script, and storyboard.

## Costs
Each run uses OpenAI API tokens for the sampled images and generated scene plan. API usage is billed separately from a ChatGPT subscription. The workflow uses `gpt-5-mini` by default. Check the OpenAI API pricing page and usage dashboard before running repeated tests.

## Local run
Requires Python 3.11, FFmpeg, and internet access. Set `OPENAI_API_KEY` in your environment, install requirements, and run:
```bash
pip install -r requirements.txt
python make_ad.py --product "Vitamin C Serum" --audience "women interested in skincare" --problem "dull-looking skin" --benefit "a simple serum step for a skincare routine" --cta "Learn more"
```

## Notes
- AI voice is generated speech, not a real customer testimonial.
- Do not present scripted copy as a genuine customer review.
- Review all claims and footage before publishing.
- GitHub Actions artifacts are temporary (7-day retention); download your MP4 after the run.
