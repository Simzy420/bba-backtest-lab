# Swapr: Add template (phone fix)

## Use this URL
**https://wan22-templates.vercel.app/**

Do **not** use `swapr-casey.netlify.app` (no Add template) and do **not** rely on the tiny iframe inside Command Center — open Swapr in its **own tab**.

## How to add a template on your phone
1. Open https://wan22-templates.vercel.app/ in Safari/Chrome (new tab).
2. Tap the dashed **Add template video** box under Motions.
3. Pick a ~3–5s clip from Photos/Files (larger phone clips are OK; Generate compresses them).
4. Your clip appears in the rail — select it, upload a still, Generate.

## What we fixed (latest deploy)
- Big tappable **label** drop zone (iOS often ignored the old hidden-input button click)
- Gallery accepts larger phone videos (up to ~50 MB)
- Generate compresses oversized clips before upload (API budget ~3.5 MB)
