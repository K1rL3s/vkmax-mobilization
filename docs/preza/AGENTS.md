# AGENTS.md

How to build and edit the "Жэка Коммуналкин" pitch deck. `CLAUDE.md` is a symlink to this file.

## Commands

```
npm ci        # pinned pptxgenjs, sharp, react-icons, jszip
npm run build # node build.js -> zheka.pptx
./render.sh   # build + zheka.pdf + build/slides/slide-NN.jpg
```

`render.sh` needs LibreOffice (`soffice` on `PATH`, or its path in `SOFFICE`) and `pdftoppm` from Poppler. `zheka.pdf` is the committed deck; `zheka.pptx` is its source for manual touch-ups.

The submitted PDF carries the commit hash and the API test token on slide 1, and the token must never reach the repository. Render it into the ignored `build/`:

```
OUT=build/submission COMMIT=<hash> API_TEST_TOKEN=<token> ./render.sh   # -> build/submission.pdf
```

Fonts: Unbounded (headings) and Manrope (body) must be installed as static instances (Regular, Bold). Variable builds render at their thinnest weight in LibreOffice and PowerPoint. `render.sh` writes its own `build/fonts.conf`, because headless LibreOffice on macOS otherwise sees no user fonts and falls back to serif.

## Editing

- All content lives in `build.js`: one `{ ... }` block per slide, in deck order. Slide numbers come from the `n` counter, so adding or removing a block renumbers the rest.
- The team is the `TEAM` constant. The deck shows names and roles only; GitHub links live in the root `README.md`.
- Layout helpers: `lightSlide`/`darkSlide` (background, stripe corner, number), `title`, `text`, `card` (sticker card with a hard shadow), `badge` (lucide icon in a circle; names come from `react-icons/lu`), `says` (Zheka's speech bubble with his avatar), `bullets`, `placeholder`, `phone` (a screenshot from `screens/` in a phone frame, returns its width).
- `says` bubbles are aimed at the avatar after the build: `aimBubbles` writes the callout adjustments into the slide XML, since pptxgenjs cannot set them. The bubble text is a separate text box on top of the shape, so it stays vertically centred.
- Links must be clickable in the PDF. On light backgrounds use a text `hyperlink` run. On coloured shapes and dark slides use `link()`, a transparent image with a hyperlink laid over the text: LibreOffice repaints hyperlink text in its own blue.
- No period after the last sentence of a phrase, bullet or bubble; periods stay between sentences.
- Coordinates are inches on a 13.333 x 7.5 canvas. Keep 0.6 in margins.
- Style follows `../zheka-brandbook.md`: brand palette only, orange `vest` as a single accent per slide, text in `navy`, sentence case, no caps kickers.
- Content follows `../track/05-submission.md` and `../track/06-criteria.md`. Slide 1 is the service slide for the technical check. Keep facts sourced from `docs/` and name the source on the slide. Unknowns stay as `[placeholders]` in square brackets, never invented numbers.

## Checking

After every change run `./render.sh` and look at the changed slides in `build/slides/`: text overflow, overlaps and bubbles pointing at the avatar are what breaks most often. `markitdown zheka.pptx | grep -o '\[[^]]*\]'` lists the placeholders left to fill.
