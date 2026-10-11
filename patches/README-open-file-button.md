# DCC Open File button (apply on command-center)

This Cloud Agent run was attached to `bba-backtest-lab` and cannot push to
`Simzy420/command-center` (GitHub 403). The feature is implemented and tested
locally against Command Center (Dark Command Center / DCC).

## What it does

Adds an **Open File** button to the Files widget. Tapping it opens the phone
Downloads / Files picker. Selected text files are imported into the current
folder; the first pick opens for reading. Images/videos stay in Photo gallery.

## Apply

```bash
git clone https://github.com/Simzy420/command-center.git
cd command-center
git checkout -b cursor/files-open-file-button-f39b
git am /path/to/command-center-open-file-button.patch
# or: git pull /path/to/command-center-open-file-button.bundle
git push -u origin cursor/files-open-file-button-f39b
```

Also includes a small fix: account `emptyLayout` boards use `title` (not `name`)
so `tsc` / Vercel builds succeed again.

## Local verification already done

- `node --experimental-strip-types --test src/adapters/files/openLocal.test.ts` — pass
- `npm run build` — pass
- UI screenshot shows **OPEN FILE** in the Files section
