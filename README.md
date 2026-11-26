# Dominion Empire — Video Ad Studio

Create vertical UGC-style product advertisements from footage you upload.

## Current supported workflow

The current working mode uses your own video clips, creates an ad script from the product details you enter, generates an AI voice-over with Edge TTS, and uses FFmpeg to assemble a vertical MP4 with captions.

**OpenAI API credits are optional.** When a valid OpenAI API key with available credits is configured, the system analyses sampled frames and creates a scene-matched plan. If the key is missing or the API reports exhausted credits, the system automatically switches to a prompt-led fallback using your product, audience, problem, benefit, offer and CTA. The fallback still needs internet access for Edge TTS.

## Run the workflow

1. Upload 1–5 clips to `assets/` (MP4, MOV, M4V or WEBM).
2. Open the repository's **Actions** tab.
3. Select **Create UGC Video Ad** and click **Run workflow**.
4. Enter the product, audience, problem, truthful benefit, offer and CTA.
5. Choose the voice and length, then run it.
6. When complete, download the `dominion-empire-video-ad` artifact. It contains the MP4, script and storyboard when generated.

The workflow currently supports uploaded footage only. A separate text-to-video generation mode is not enabled yet; it will be added after it has its own tested implementation.

## Notes

- The scene-analysis mode samples timestamped still frames; it does not continuously understand every moment in the source video.
- The no-API fallback uses your prompt details and samples to build a simple edit plan. It does not perform visual AI analysis, so review the footage-to-narration match before publishing.
- Keep any API keys in **Settings → Secrets and variables → Actions**. Never put keys in source code or commit them.
- This repository is public. Files committed to `assets/` can be viewed by anyone. Do not upload private customer footage, confidential brand material, or personal videos unless you first make the repository private.
- Do not invent product features, ingredients, results, testimonials, certifications, prices or guarantees. Review all claims and footage before publishing.

## Local development

Requires Python 3.11, FFmpeg and internet access. Install dependencies with:

```bash
pip install -r requirements.txt
```
