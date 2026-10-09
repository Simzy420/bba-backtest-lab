# Swapr: Add template button

This folder holds a ready patch for **Simzy420/wan22-templates** (the Swapr / Become the Character app at https://swapr-casey.netlify.app).

This Cloud Agent run is bound to **bba-backtest-lab** and cannot push to `wan22-templates`. Apply the patch in that repo (or re-run the agent there) to ship to Netlify.

## What you get

An **Add template** button next to **Refresh** in the Motions section. Tap it, pick a short MP4/MOV (about 3–5s, max ~2.5 MB), and the clip appears in the gallery for this session. Generate sends it to Runpod as `video_base64`.

## Apply

```bash
cd wan22-templates
git apply path/to/0001-add-template-button.patch
# or: git am 0001-add-template-button.patch
git push
```

Netlify (swapr-casey) redeploys from that repo’s main branch.
