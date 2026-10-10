# Swapr: Add template button

## Why upload failed in Dark Command Center

Command Center’s Swapr tab was opening **https://swapr-casey.netlify.app**, which never got the **Add template** button. The button only shipped on the Vercel app.

Also: on iPhone, picking a video/photo **inside the embedded iframe** often does nothing — use **Open Swapr** (new tab).

## Working now

1. Open **https://wan22-templates.vercel.app/** (or Command Center → Swapr → **Open Swapr** once that host points here).
2. Motions → **Add template** → pick a ~3–5s MP4/MOV under ~2.5 MB.
3. Select the clip → upload your still → Generate.

## Production status

| Host | Add template |
|------|----------------|
| https://wan22-templates.vercel.app | Yes |
| https://swapr-casey.netlify.app | No (old build) |
| https://simzy420.github.io/command-center/ | Still opens Netlify until `command-center` main is updated |
| https://command-center-caseylsims-2615.vercel.app | Updated to open Vercel Swapr |

## Apply patches

- `0001-add-template-button.patch` → repo **wan22-templates** (merge branch `cursor/add-template-button-2feb` to `main` for Netlify too)
- `command-center/0001-point-swapr-at-vercel.patch` → repo **command-center** (points Swapr at the Vercel app)
