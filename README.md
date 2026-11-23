# Dominion Empire — AI Video Ad Studio

Create vertical product ads in two ways:

1. **AI-generated moving video:** Enter your product and audience. OpenAI plans the advert scene by scene, Runway generates actual moving video clips from text prompts, Edge TTS creates the voice-over, and FFmpeg combines the scenes into a vertical MP4.
2. **Use your own footage:** Upload clips to `assets/` and let OpenAI analyse sampled frames to match narration to the most relevant footage.

## AI-generated moving video

This mode does not require you to upload any video footage. It generates new moving scenes from text prompts.

### Required API keys

Add these under **Settings → Secrets and variables → Actions**:

- `OPENAI_API_KEY`: your OpenAI API key for the script and scene plan.
- `RUNWAYML_API_SECRET`: your Runway Dev API key for actual video generation.

Keep both keys private. Never put them in source code or commit them.

### Video-generation cost

The default model is Runway's Seedance 2.5 at 720p. Runway currently lists this at about **$0.30 per generated second**. Approximate generation costs before taxes or retries:

| Ad length | Estimated video-generation cost |
|---|---:|
| 15 seconds | $4.50 |
| 25 seconds | $7.50 |
| 35 seconds | $10.50 |

OpenAI API usage is separate and usually much smaller than the video-generation charge. Failed or repeated generations may affect the final amount; check your Runway balance and usage before running. A ChatGPT subscription does not pay for either API.

**Important product-accuracy limitation:** Text-to-video can create realistic moving scenes, but it may invent packaging details or render brand labels incorrectly. The generated footage is not a guarantee that the exact real product package will appear. A later product-reference-image option can improve product consistency without requiring you to upload video.

## Run the workflow

1. Open the repository's **Actions** tab.
2. Select **Create UGC Video Ad** and click **Run workflow**.
3. Choose `ai_generated` to create moving scenes from scratch, or `uploaded_footage` to edit clips you uploaded.
4. Enter the product, audience, problem, truthful benefit, offer and CTA.
5. Choose the voice and length, then run it.
6. When complete, download the `dominion-empire-video-ad` artifact. It contains the MP4, script and storyboard.

## Uploaded-footage mode

Upload 1–5 clips to `assets/` (MP4, MOV, M4V or WEBM). The model analyses timestamped still frames sampled from the clips, not the original video continuously. It can miss fast actions or details between sampled frames. Review the storyboard and final video before publishing.

**Repository visibility:** This repository is public. Files committed to `assets/` can be viewed by anyone. Do not upload private customer footage, confidential brand material, or personal videos unless you first make the repository private.

## Truthful advertising

- Do not invent product features, ingredients, results, testimonials, certifications, prices or guarantees.
- AI voice is generated speech, not a real customer testimonial.
- Do not present a generated actor as a real customer.
- Review all claims and footage before publishing.

## Local development

Requires Python 3.11, FFmpeg and internet access. Install dependencies with:

```bash
pip install -r requirements.txt
```

The GitHub Actions workflow is the simplest way to generate and download an ad.
