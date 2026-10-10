# Point Dark Command Center Swapr at Vercel

## Status (2026-10-10)

**Live now:** https://command-center-neon-iota.vercel.app Image gen → Swapr opens
**https://wan22-templates.vercel.app/** (production file deploy).

`Simzy420/command-center` **git `main` still has the Netlify URL**. The next git-triggered
Vercel deploy from `main` would revert this unless that source change is merged.

## Source change

`SWAPR_APP_URL` → `https://wan22-templates.vercel.app/`

Files:
- `src/adapters/swapr.ts`
- `src/components/widgets/SwaprPanel.tsx` (prefer Open Swapr for phone uploads)
- `src/lib/embedFrame.test.ts`
- `README.md`

## Apply to `Simzy420/command-center` (required to stick)

This Cloud Agent environment can only push to `bba-backtest-lab`. On a checkout with
write access to command-center:

```bash
cd command-center
git checkout -b cursor/swapr-vercel-url
git apply /path/to/0001-point-swapr-at-vercel.patch
git add src/adapters/swapr.ts src/components/widgets/SwaprPanel.tsx src/lib/embedFrame.test.ts README.md
git commit -m "Point Image gen Swapr button at wan22-templates.vercel.app"
git push -u origin HEAD
```

Or re-run a Cloud Agent **on the command-center repo** with:
“Point the Image gen Swapr button at https://wan22-templates.vercel.app/”
