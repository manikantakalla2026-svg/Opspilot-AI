# Gemini model catalog returned for the configured key

7 November 2026. Exactly one authenticated read-only models.list request; no
further pages, retries, content generation, incident data or billing changes.
The response had no next-page token. Listing is not proof of project-specific
generation access, free quota, billing tier or structured-output acceptance.

## Advertised generateContent support (47)

- `gemini-2.5-flash`
- `gemini-2.5-pro`
- `gemini-2.5-flash-preview-tts`
- `gemini-2.5-pro-preview-tts`
- `gemma-4-26b-a4b-it`
- `gemma-4-31b-it`
- `gemini-flash-latest`
- `gemini-flash-lite-latest`
- `gemini-pro-latest`
- `gemini-2.5-flash-lite`
- `gemini-2.5-flash-image`
- `gemini-3-flash-preview`
- `gemini-3.1-pro-preview`
- `gemini-3.1-pro-preview-customtools`
- `gemini-3.1-flash-lite-preview`
- `gemini-3.1-flash-lite`
- `gemini-3-pro-image-preview`
- `gemini-3-pro-image`
- `nano-banana-pro-preview`
- `gemini-3.1-flash-image-preview`
- `gemini-3.1-flash-image`
- `gemini-3.1-flash-lite-image`
- `gemini-nano-banana-2.1`
- `gemini-3.5-flash`
- `gemini-3.5-flash-lite`
- `gemini-omni-flash-preview`
- `gemini-omni-1.1-flash`
- `gemini-omni-1.2-flash`
- `gemini-3.5-transcribe`
- `gemini-3.6-flash`
- `gemini-3.7-flash`
- `gemini-3.8-flash`
- `gemini-4-argon`
- `lyria-3-clip-preview`
- `lyria-3-pro-preview`
- `lyria-3.5`
- `gemini-3.1-flash-tts-preview`
- `gemini-3.8-flash-tts`
- `gemini-3.8-flash-lite-tts`
- `gemini-robotics-er-2-preview`
- `gemini-2.5-computer-use-preview-10-2025`
- `antigravity-preview-05-2026`
- `antigravity-preview-09-2026`
- `antigravity-preview-latest`
- `deep-research-max-preview-04-2026`
- `deep-research-preview-04-2026`
- `deep-research-pro-preview-12-2025`

## No advertised generateContent support (14)

- `gemini-embedding-001`
- `gemini-embedding-2-preview`
- `gemini-embedding-2`
- `aqa`
- `gemini-3.5-transcribe-live`
- `gemini-2.5-flash-native-audio-latest`
- `gemini-2.5-flash-native-audio-preview-09-2025`
- `gemini-2.5-flash-native-audio-preview-12-2025`
- `gemini-3.1-flash-live-preview`
- `gemini-3.8-live`
- `gemini-3.8-live-extended-thinking`
- `gemini-robotics-er-2-streaming-preview`
- `gemini-3.5-live-translate-preview`
- `lyria-realtime-exp`

## Recommendation

Use `GEMINI_MODEL=gemini-3.5-flash-lite` for a separately approved next test.
It is listed with generateContent support, and Google documents structured
outputs and free standard input/output pricing. This is a suitability
recommendation, not successful live generation verification.

The previous model `gemini-2.5-flash-lite` is also in this catalog, despite
the observed 404 on generation. Therefore that response cannot be interpreted
as proof that the name is universally absent; model-list success alone does
not resolve the earlier generation failure. No environment settings were changed.

References: [Google pricing](https://ai.google.dev/gemini-api/docs/pricing)
and [model capabilities](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite).
