# Study Notes

A static collection of course study guides: Chinese explanations, worked examples, formulas and self-tests. Some guides are bilingual, with every Chinese paragraph followed by an English one. An independent study resource, not an official NUS website or past-exam archive.

## Notes in this site

| Course | Page | What is in it |
| --- | --- | --- |
| CS5340 Uncertainty Modelling in AI | `cs5340-study.html`, `cs5340/*.svg` | Lecture 1–10 explained page by page in Chinese for beginners, every worked example computed step by step, a Chinese–English glossary at the end of each lecture, all 18 Exercise 1 questions with folded solutions and English model answers, a one-page tour of all ten lectures and a final formula sheet. |
| CS5242 Neural Networks and Deep Learning | `cs5242-study.html` | Lecture 1–10, Assignment 1 derivations, Quiz 7–10 solutions, exam checklist, formula sheet, 22 self-test questions. Chinese–English, paragraph by paragraph. |
| CS5234 Algorithms at Scale | `cs5234-study.html`, `cs5234/*.pdf` | Lecture 1–11 explained in Chinese for beginners, homework and take-home walkthroughs, Quiz 1 and Quiz 2 cheat sheets (Chinese and English PDFs), mock papers in the formal quiz format with marking points, and a bilingual practice bank. Quiz 2 material excludes k-means. |
| CS5228 Knowledge Discovery and Data Mining | `cs5228-study.html`, `cs5228-practice.html`, `cs5228-bilingual-cheat-sheet.pdf` | Lecture 1–6 study guide with interactive labs, practice exercises and a printable bilingual cheat sheet. |

`index.html` is the hub that lists every note. Old links to the CS5228 guide still work: the CS5228 file names are unchanged, and the hub forwards the old `#lecture1`-style section links.

## Layout

- `index.html` – the hub (generated)
- `cs5242-study.html` – CS5242 guide (generated from `notes-src/cs5242.md`)
- `cs5340-study.html`, `cs5340/` – CS5340 guide (generated from `notes-src/cs5340.md`) and its diagrams
- `cs5234-study.html`, `cs5234/` – the CS5234 guide (hand-written page) and its PDFs
- `cs5228-*.html`, `cheat-page-*.png`, `cs5228-bilingual-cheat-sheet.pdf` – the CS5228 guide (hand-written, unchanged apart from a link back to the hub)
- `assets/site.css`, `assets/notes.js` – shared styles and runtime for generated guides
- `assets/katex/` – KaTeX stylesheet and fonts for the pre-rendered formulas (MIT licence in `assets/katex/LICENSE`)
- `notes-src/` – note sources: `catalog.json` lists every note shown on the hub; each generated note has a Markdown file and a JSON config
- `tools/build_notes.py`, `tools/katex_render.js` – the generator

## Adding or updating a note

1. Write the note in Markdown under `notes-src/` (see `cs5242.md` for the conventions):
   - `##` is a page; for the section named in the config's `split` list, each `###` under it becomes its own page
   - a line that is only `**bold**` is a section heading; numbered ones (`**1. …**`) are main headings
   - an `*italic*` paragraph right after a Chinese paragraph is its English translation (hidden by the “只看中文” button)
   - `中文 · English` in headings and table cells is shown on two lines
   - ```` ```latex ```` blocks are rendered with KaTeX when the site is built
   - a question list, then a heading starting with `答案`, then an answer list: each answer is folded under its question
   - any other heading starting with `答案` folds everything up to the next heading of the same or a higher level
   - images are ordinary Markdown images (`![说明](cs5340/figure.svg)`), with paths relative to the site root
2. Add a config next to it (copy `notes-src/cs5242.json`): output file, page order, sidebar labels, card descriptions. Optional keys: `"subsections": true` keeps `**3.1 …**` bold lines (and unnumbered ones on pages that have `###` sections) as subheadings instead of promoting them; `metrics` adds figures to the overview hero; `overview_head` replaces the heading above the chapter cards. The accent can be `green`, `blue` or `plum`.
3. Add an entry to `notes-src/catalog.json` with `source` and `config`.
4. Build: `python3 tools/build_notes.py` (needs Python with `markdown-it-py`, `beautifulsoup4`, `lxml`, and Node.js with the `katex` package; set `KATEX_PATH` if `katex` is not installed where Node can find it).

A note that is a hand-written page (like CS5228) only needs a catalog entry without `source`.

## Hosting

Serve these files as a static site. For GitHub Pages, select Settings → Pages → Deploy from a branch → main → /(root).

Progress, practice answers and the reading-mode choice are stored only in the visitor's browser. Original lecture slides and private files are not included. Linked external materials retain their original authorship.
