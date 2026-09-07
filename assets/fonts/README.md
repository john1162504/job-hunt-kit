# Fonts for resume PDF export

Use the full Arial TTF files only:

- `Arial-Regular.ttf`
- `Arial-Bold.ttf`
- `Arial-Bold-Italic.ttf`

On macOS, if these are missing or corrupt, run:

```bash
./scripts/ensure_fonts.sh
```

That copies from `/System/Library/Fonts/Supplemental/`.

## Subset fonts (do not use)

Files such as `BCDFEE_Arial-BoldMT.ttf` were extracted from a sample master PDF and omit common glyphs. They are kept for reference only and must **not** be referenced by `render_resume_pdf.py`.
