<div align="center">

<sub>BUILT FROM FIRST PRINCIPLES</sub>

# A Library

**Long-form books that show their working — each one beginning at the beginning,
deriving what it uses, and marking what it does not.**

### [→ Read the library](https://elkhanany.github.io/library/)

</div>

---

## The books

| | | |
|---|---|---|
| **[From Newton to M-Theory](books/newton-to-mtheory/)** | Special relativity through to strings, derived rather than quoted. | 37 of 76 chapters |
| **[The Long Argument](books/the-long-argument/)** | Eight philosophical questions that opened early and never closed, read as conversations across centuries. | index and 117 studies built, 8 chapters planned |

Each book keeps its own conventions, its own register of what it has taken on trust, and its own
plans and review reports, because those are properties of a book rather than of the machinery. What
they share is the machinery.

## Why one repository

The build system is not finished furniture. In a single recent stretch `tagcheck` learned to reject
a macro used with an argument it does not take, `xrefcheck` learned to audit the ledger, and
`book.js` gained a snapshot API so an animated figure could not bake a different frame into every
build. Held in two repositories, each of those improvements would have to be ported by hand, and the
copy that missed one would rot quietly. One repository also means one published site, so the shelf
below is a real front door rather than a third repository pretending to be one.

## Layout

```
tools/                the build system, shared by every book
  library.py          resolves the repository, loads each book.json
  build.py            assembles src/ fragments into whole pages
  make.py             the offline build   → build/<book>/   (self-contained)
  webbuild.py         the website build   → docs/           (GitHub Pages)
  verify.py           audits built pages with all network blocked
  throughline.py      extracts the plain-language layer
  xrefcheck.py        proves every cross-reference resolves
  tagcheck.py         malformed HTML, and maths that browsers eat silently
  registercheck.py    proves a prose rewrite changed only prose
  debts.py            collects the promises earlier chapters make
  figcheck.py         loads and exercises every interactive figure
  sitecheck.py        every link in the published site resolves, across books

shared/
  assets/             the house style — book.css, book.js
  vendor/katex/       KaTeX, vendored so no page needs the network

books/<slug>/
  book.json           title, theme, and which machinery this book wants
  curriculum.json     the chapter list — the plan of record
  src/                the chapters, as HTML fragments. The only hand-edited files.
  CONVENTIONS.md      how this book is written
  plans/ reports/     its curriculum and its independent reviews

docs/                 the published site, committed deliberately
  index.html          the library hub
  <slug>/             one directory per book
```

## Building

```bash
pip install playwright && playwright install chromium
```

```bash
python3 tools/webbuild.py     # the whole library → docs/
python3 tools/verify.py       # audit one book's build, network blocked
python3 tools/sitecheck.py    # every link across the whole site
```

On Windows, run with `PYTHONUTF8=1`. The chapters contain ⚑ and −, and the platform's default
encoding is cp1252, which cannot read them.

Both builds render the mathematics **at build time** in headless Chromium and write the finished DOM
to disk, so nothing is typeset in the reader's browser: pages paint immediately and work with the
network switched off. All output is written UTF-8 with LF endings regardless of platform, so the
same source builds to the same bytes anywhere.

## Adding a book

Create `books/<slug>/` with a `book.json` and a `curriculum.json`, put chapter fragments in `src/`,
and add the slug to `ORDER` in `tools/library.py`. Nothing else needs to know it exists — the hub,
the navigation and the build all read the manifest.

`book.json` declares what the book actually wants:

```json
{
  "slug": "the-long-argument",
  "title": "The Long Argument",
  "shell": "minimal",
  "features": { "math": false, "ledger": false, "throughline": false },
  "theme": { "accent": "#a3232b", "field": "marginalia" }
}
```

A book with no equations in it does not inherit KaTeX, equation numbering, the Math Ledger or the
flag register merely by being a neighbour, and its top bar does not advertise pages it will never
have. The theme drives the hub: hovering a book on the shelf washes the whole page in its colour.

## The standard every book is held to

`verify.py` opens every built page at desktop and phone widths **with all network requests blocked**,
and fails if any equation did not typeset, any cross-reference did not resolve, any mathematics
overflows its column, or any page reaches for the internet. `docs/` is committed rather than built by
an Action, so what is published is exactly the bytes that passed.
