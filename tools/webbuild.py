#!/usr/bin/env python3
"""
Emit docs/ — the GitHub Pages site.

Differs from build/ in one way that matters: the website shares one stylesheet and
one set of maths fonts across every page instead of inlining them into each file.
That is wrong for Dropbox (where each file is previewed in isolation and relative
paths do not resolve) and right for a web server (where the browser caches them
once). Same source, two targets, no duplicated content.
"""
import os, re, shutil, html, importlib.util, asyncio
from playwright.async_api import async_playwright

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import library

ROOT = library.ROOT
STAGE = os.path.join(ROOT, ".webstage")
DOCS = library.DOCS
VEND = os.path.join(library.VENDOR, "katex")
BOOK = None                 # set per book by build_book()

spec = importlib.util.spec_from_file_location("bp", os.path.join(os.path.dirname(os.path.abspath(__file__)), "build.py"))
bp = importlib.util.module_from_spec(spec); spec.loader.exec_module(bp)

def mathcss(bk):
    """A book with no equations ships no KaTeX, so it must not ask for it."""
    return ('<link rel="stylesheet" href="assets/katex.min.css">'
            if bk.has("math") else "")


def nav(bk):
    """The book's own top bar, plus the way back to the library.

    Built from the book's features rather than fixed, so a book with no ledger
    and no through-line does not advertise two pages it will never have.
    """
    links = ['<a href="contents.html">Chapters</a>']
    if bk.has("throughline"):
        links.append('<a href="throughline.html">In Plain Terms</a>')
    if bk.has("ledger"):
        links.append('<a href="ledger.html">Math Ledger</a>')
    links.append('<a href="../index.html">Library</a>')
    return """<nav class="topnav">
  <a class="brand" href="index.html">{brand}</a>
  <div class="topnav-links">
    {links}
  </div>
</nav>""".format(brand=bk.brand, links="\n    ".join(links))


SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — {book}</title>
<meta name="description" content="{desc}">
{mathcss}
<link rel="stylesheet" href="assets/book.css">
</head>
<body>
{nav}
<div class="wrap">
<nav class="sidebar">
  <a class="sb-home" href="contents.html">← All chapters</a>
  <p class="sb-title">{sbhead}</p>
  <div id="sb-toc">{toc}</div>
</nav>
<main class="main">
<div class="col{wide}">
{body}
</div>
</main>
</div>
<script src="assets/book.js"></script>
{extra}
</body>
</html>
"""


def runtime_js():
    js = library.read(os.path.join(library.ASSETS, "book.js"))
    js = js.replace("numberEquations();", "/* numbered at build time */")
    js = re.sub(r"if \(window\.katex\) \{ typeset\(\); \}.*?\n  \}\);", "});", js, flags=re.S)
    return js


ARC = [
    ("Part 0",   "The Toolkit",
     "Numbers describe a thing only relative to a choice. The useful description is the one "
     "in which a hard problem falls apart into independent pieces."),
    ("Part I",   "The Action Principle",
     "Forces are the wrong primitive. Attach one number to each possible history, and nature "
     "selects the history where that number stops changing."),
    ("Part II",  "Special Relativity",
     "The speed limit is built into the geometry, not the materials. Magnetism turns out to be "
     "electricity, seen from a moving frame."),
    ("Part III", "General Relativity",
     "Gravity is not a force but the shape of the arena. Free fall is the straightest available "
     "motion."),
    ("Part IV",  "Quantum Mechanics",
     "\u201cWhat state is this in\u201d stops having a single answer. The mathematics was already "
     "built in Part\u00a00."),
    ("Part V",   "Quantum Field Theory",
     "Particles stop being fundamental. The field is; particles are its excitations, the way "
     "notes are excitations of a string."),
    ("Part VI",  "Gauge Theory",
     "Demand a symmetry hold locally rather than globally, and a force appears to enforce it. "
     "Every force is that one demand."),
    ("Part VII", "Strings and M-Theory",
     "Gravity refuses the treatment that worked for everything else \u2014 followed by an honest "
     "account of what is known and what is conjecture."),
]


WORDCOUNT_JS = """() => {
                const d = document.querySelector('.main .col').cloneNode(true);
                d.querySelectorAll('.katex, script, style').forEach(e => e.remove());
                return (d.textContent.match(/[A-Za-z0-9\u2019'-]+/g) || []).length; }"""


def landing_page(bk, stats):
    """docs/<slug>/index.html — the book's own front door, generated so its
    counts can never go stale. A book supplies src/_landing.html; without one
    it gets a plain cover built from book.json."""
    tplf = os.path.join(bk.src, "_landing.html")
    if not os.path.exists(tplf):
        library.write(os.path.join(bk.out, "index.html"),
            SHELL.format(mathcss=mathcss(bk), title="Contents", desc=html.escape(bk.tagline), nav=nav(bk),
                         sbhead="Parts", toc="", wide=" wide", extra="",
                         book=html.escape(bk.title),
                         body=f'<p class="eyebrow">{html.escape(bk.eyebrow)}</p>'
                              f'<h1>{html.escape(bk.title)}</h1>'
                              f'<p class="subtitle">{html.escape(bk.tagline)}</p>'
                              f'<p>{bk.cfg.get("blurb", "")}</p>'
                              f'<p><a href="contents.html">All chapters &rarr;</a></p>'))
        return 0

    tpl = library.read(tplf)

    built = {}          # part index -> (chapters written, chapters planned)
    for i, (_pt, _blurb, chs) in enumerate(bp.PARTS):
        done = sum(1 for c in chs if os.path.exists(bk.chapter_path(c[1])))
        built[i] = (done, len(chs))

    rows = []
    for i, (k, title, blurb) in enumerate(ARC):
        done, total = built.get(i, (0, 0))
        live = done > 0
        tag = "a" if live else "div"
        href = ' href="contents.html#sec-%d"' % i if live else ""
        cls = "arc-row" if live else "arc-row pending"
        count = ("%d of %d chapters" % (done, total)) if live else ("%d chapters" % total)
        rows.append(
            '<{t} class="{c}"{h}><div class="arc-k">{k}</div>'
            '<div class="arc-b"><div class="arc-t">{ti}</div><p>{b}</p></div>'
            '<div class="arc-n">{n}</div></{t}>'.format(
                t=tag, c=cls, h=href, k=k, ti=title, b=blurb, n=count))

    for key, val in stats.items():
        tpl = tpl.replace("{{%s}}" % key, val)
    tpl = tpl.replace("{{ARC}}", "\n".join(rows))
    library.write(os.path.join(bk.out, "index.html"), tpl)
    return len(rows)


HUB_CSS = """
*{box-sizing:border-box}
:root{
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,Charter,Georgia,Cambria,serif;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif;
  --ink:#16181d; --ink-soft:#565b66; --ink-faint:#878d99; --rule:#dcdfe5;
}
html,body{margin:0;height:100%}
body{
  font-family:var(--serif); color:var(--ink); background:#f4f3f0;
  -webkit-font-smoothing:antialiased; position:relative; overflow-x:hidden;
  -webkit-text-size-adjust:100%; text-size-adjust:100%;
}

/* ---------- the field ----------
   One layer per book, all stacked, all transparent until that book is asked
   for. Hovering a tile does not swap an image; it fades one layer up and the
   others down, so the whole page takes on the book's weather.

   Every layer is translucent and mixed from the book's own accent, so the
   wash tints whatever the page is already standing on. That is what makes it
   survive dark mode: an opaque near-white gradient here would flash the whole
   page white the moment a pointer crossed a tile. Nothing is opaque, so
   nothing can. --w1..--wg are the alphas, lifted in dark mode because a tint
   has to work harder against a dark ground to be seen at all. */
:root{--w1:.30;--w2:.20;--w3:.075;--wg:.07;--wt:.11}
.field{position:fixed;inset:0;z-index:0;opacity:0;transition:opacity .55s ease;pointer-events:none;
  --fg:var(--a-rgb); --fg2:var(--a2-rgb)}
.field.base{opacity:1;background-image:radial-gradient(120% 80% at 50% -10%,rgba(90,96,110,.05) 0%,transparent 60%)}
body[data-focus] .field.base{opacity:0}

/* the three weathers a book can ask for, drawn from its own accent */
.field[data-style="lightcone"]{
  background-image:
    radial-gradient(125% 95% at 50% 108%, rgba(var(--fg),var(--w1)) 0%, rgba(var(--fg),calc(var(--w1)*.28)) 40%, transparent 68%),
    radial-gradient(120% 90% at 50% -8%, rgba(var(--fg2),var(--w2)) 0%, transparent 62%),
    linear-gradient(90deg, rgba(var(--fg),var(--w3)) 1px, transparent 1px),
    linear-gradient(rgba(var(--fg),var(--w3)) 1px, transparent 1px),
    linear-gradient(180deg, rgba(var(--fg),var(--wg)), rgba(var(--fg2),calc(var(--wg)*1.6)));
  background-size:auto,auto,46px 46px,46px 46px,auto}
.field[data-style="marginalia"]{
  background-image:
    linear-gradient(90deg,transparent 0 7.3%,rgba(var(--fg),var(--wt)) 7.3% 7.75%,transparent 7.75%),
    repeating-linear-gradient(180deg,transparent 0 33px,rgba(var(--fg2),var(--w3)) 33px 34px),
    radial-gradient(95% 75% at 82% -4%, rgba(var(--fg),var(--w1)) 0%, transparent 62%),
    radial-gradient(85% 65% at 8% 104%, rgba(var(--fg2),var(--w2)) 0%, transparent 60%),
    linear-gradient(180deg, rgba(var(--fg),var(--wg)), rgba(var(--fg2),calc(var(--wg)*1.6)))}
.field[data-style="plain"]{
  background-image:
    radial-gradient(95% 75% at 70% -4%, rgba(var(--fg),var(--w1)) 0%, transparent 62%),
    linear-gradient(180deg, rgba(var(--fg),var(--wg)), rgba(var(--fg2),calc(var(--wg)*1.6)))}
BOOKFIELDS

.wrap{position:relative;z-index:1;max-width:64rem;margin:0 auto;padding:clamp(2.5rem,7vh,5rem) 1.4rem 4rem}

header.lede{max-width:38rem;margin:0 0 clamp(2rem,5vh,3.4rem)}
.eyebrow{font-family:var(--sans);font-size:.7rem;font-weight:700;letter-spacing:.22em;
  text-transform:uppercase;color:var(--ink-faint);margin:0 0 .9rem}
h1{font-size:clamp(2.1rem,5.2vw,3.3rem);line-height:1.04;letter-spacing:-.025em;
  font-weight:600;margin:0 0 1rem}
.lede p{font-size:clamp(1rem,2vw,1.14rem);line-height:1.6;color:var(--ink-soft);margin:0;max-width:34rem}

/* ---------- the shelf ---------- */
.shelf{display:grid;grid-template-columns:repeat(2,1fr);gap:1.15rem}
@media (max-width:760px){.shelf{grid-template-columns:1fr}}

.book{
  position:relative;display:flex;flex-direction:column;justify-content:space-between;
  min-height:19rem;padding:1.6rem 1.5rem 1.35rem;
  text-decoration:none;color:inherit;
  background:rgba(255,255,255,.72);
  border:1px solid var(--rule);border-radius:10px;
  -webkit-backdrop-filter:saturate(140%) blur(6px);
  backdrop-filter:saturate(140%) blur(6px);
  transition:transform .3s ease,box-shadow .3s ease,opacity .4s ease,
             border-color .3s ease,background .4s ease;
}
.book:hover,.book:focus-visible{
  transform:translateY(-3px);
  border-color:var(--bk-accent);
  box-shadow:0 14px 40px rgba(20,22,28,.14);
  outline:none;
}
/* the other books recede rather than disappear — still readable, plainly not the subject */
body[data-focus] .book{opacity:.34;filter:saturate(.5)}
body[data-focus] .book[data-live="1"]:hover,
body[data-focus] .book[data-live="1"]:focus-visible{opacity:1;filter:none}

.book .rule{width:2.4rem;height:3px;border-radius:2px;background:var(--bk-accent);margin:0 0 1.1rem}
.book .kicker{font-family:var(--sans);font-size:.66rem;font-weight:700;letter-spacing:.18em;
  text-transform:uppercase;color:var(--bk-accent);margin:0 0 .6rem}
.book h2{font-size:clamp(1.5rem,3.1vw,2rem);line-height:1.08;letter-spacing:-.02em;
  font-weight:600;margin:0 0 .7rem}
.book p{font-size:.95rem;line-height:1.55;color:var(--ink-soft);margin:0}
.book .foot{display:flex;align-items:baseline;justify-content:space-between;gap:1rem;
  margin-top:1.5rem;font-family:var(--sans);font-size:.78rem;color:var(--ink-faint)}
.book .count{font-weight:650;color:var(--ink-soft)}
.book .go{color:var(--bk-accent);font-weight:650}
.book[data-live="0"]{cursor:default}
.book[data-live="0"] .go{color:var(--ink-faint)}

footer{margin-top:3rem;font-family:var(--sans);font-size:.76rem;color:var(--ink-faint)}
footer a{color:inherit}

@media (prefers-reduced-motion:reduce){
  .field,.book{transition:none}
  .book:hover,.book:focus-visible{transform:none}
}
/* A phone cannot hover, so the wash never fires there and the tiles have to
   carry their own colour. Apple's 44pt minimum and the home indicator are the
   other two things a desktop layout forgets. */
@media (pointer:coarse){
  .book{min-height:16rem}
  .book:active{transform:scale(.995)}
  footer a{display:inline-flex;align-items:center;min-height:44px}
  .wrap{padding-left:max(1.4rem,env(safe-area-inset-left));
        padding-right:max(1.4rem,env(safe-area-inset-right));
        padding-bottom:calc(4rem + env(safe-area-inset-bottom))}
}
@media (max-width:520px){
  .shelf{gap:.9rem}
  .book{min-height:14rem;padding:1.3rem 1.2rem 1.15rem}
}
@media (prefers-color-scheme:dark){
  :root{--ink:#e6e6e2;--ink-soft:#a9adb6;--ink-faint:#787d87;--rule:#31353d;
        --w1:.40;--w2:.30;--w3:.11;--wg:.13;--wt:.17}
  body{background:#101216}
  .book{background:rgba(24,27,32,.66)}
  /* the accents were chosen against paper; on a dark ground the book's lighter
     variant is the one that reads, so the two swap roles. */
  .field{--fg:var(--a2-rgb); --fg2:var(--a-rgb)}
  .field.base{background-image:radial-gradient(120% 80% at 50% -10%,rgba(150,160,180,.06) 0%,transparent 60%)}
}
"""

HUB_JS = """
(function () {
  var body = document.body;
  function focusBook(slug) {
    if (slug) body.setAttribute('data-focus', slug);
    else body.removeAttribute('data-focus');
  }
  document.querySelectorAll('.book').forEach(function (el) {
    var slug = el.getAttribute('data-slug');
    el.addEventListener('mouseenter', function () { focusBook(slug); });
    el.addEventListener('focus', function () { focusBook(slug); });
    el.addEventListener('mouseleave', function () { focusBook(null); });
    el.addEventListener('blur', function () { focusBook(null); });
  });
  document.querySelector('.shelf').addEventListener('mouseleave', function () { focusBook(null); });
})();
"""


def _rgb(hexcolour):
    """"#a3232b" -> "163,35,43", so a stylesheet can vary the alpha on it."""
    h = hexcolour.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "%d,%d,%d" % tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _field_css(bk):
    """A background for one book, mixed from its own accent.

    Only the two colours are emitted here; the gradients themselves live in
    HUB_CSS, keyed off data-style. That split is what lets the dark-mode block
    restyle every book's weather at once instead of once per book, and it is
    why the wash is a tint of the page rather than a sheet laid over it."""
    t = bk.theme
    a = t.get("accent", "#333333")
    a2 = t.get("accent_dark", a)
    return (f'.field[data-book="{bk.slug}"]{{--a-rgb:{_rgb(a)};--a2-rgb:{_rgb(a2)}}}\n'
            f'body[data-focus="{bk.slug}"] .field[data-book="{bk.slug}"]{{opacity:1}}\n'
            f'body[data-focus="{bk.slug}"] .book[data-slug="{bk.slug}"]'
            f'{{opacity:1;filter:none;border-color:var(--bk-accent);'
            f'box-shadow:0 14px 44px -14px rgba(var(--a-rgb),.55)}}\n')


def hub(results):
    """docs/index.html — the library's front door.

    Two tiles per row, each carrying its own colour. Hovering or tabbing to one
    changes the whole page's background to that book's and lets the others
    recede, so the shelf answers "what kind of book is this" before you click.
    """
    fields, tiles = [], []
    for bk, n, stats in results:
        fields.append(_field_css(bk))
        total = len(bk.flat)
        # A book is readable when it has a front door, not when it has chapters:
        # The Long Argument is an interactive index and would otherwise be
        # unclickable on the shelf that exists to open it.
        live = os.path.exists(os.path.join(bk.out, "index.html"))
        href = f"{bk.slug}/index.html" if live else None
        count = (f"{n} of {total} chapters" if n else f"{total} chapters planned")
        go = "Read &rarr;" if live else "Not yet written"
        tag = "a" if live else "div"
        attrs = f' href="{href}"' if live else ""
        tiles.append(
            f'<{tag} class="book" data-slug="{bk.slug}" data-live="{1 if live else 0}"{attrs}'
            f' style="--bk-accent:{bk.theme.get("accent", "#333")}">'
            f'<div><div class="rule"></div>'
            f'<p class="kicker">{html.escape(bk.eyebrow)}</p>'
            f'<h2>{html.escape(bk.title)}</h2>'
            f'<p>{html.escape(bk.tagline)}</p></div>'
            f'<div class="foot"><span class="count">{count}</span>'
            f'<span class="go">{go}</span></div>'
            f'</{tag}>')

    field_divs = "".join(
        f'<div class="field" data-book="{bk.slug}" '
        f'data-style="{bk.theme.get("field", "plain")}"></div>' for bk, _n, _s in results)
    css = HUB_CSS.replace("BOOKFIELDS", "".join(fields))

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>A Library</title>
<meta name="description" content="Books built from first principles: {', '.join(html.escape(b.title) for b, _n, _s in results)}.">
<style>{css}</style>
</head>
<body>
<div class="field base"></div>
{field_divs}
<div class="wrap">
<header class="lede">
  <p class="eyebrow">Built from first principles</p>
  <h1>A library of books that show their working.</h1>
  <p>Each one begins at the beginning and derives what it uses. Where something is taken on
  trust it is marked as such, so you always know what you are standing on.</p>
</header>
<main class="shelf">
{"".join(tiles)}
</main>
<footer>Every page works with the network switched off. <a href="https://github.com/Elkhanany">Source</a>.</footer>
</div>
<script>{HUB_JS}</script>
</body>
</html>
"""
    library.write(os.path.join(DOCS, "index.html"), page)
    return len(tiles)


async def build_book(bk, browser):
    """Render one book into docs/<slug>/."""
    global BOOK
    BOOK = bk
    bp.use(bk)

    shutil.rmtree(STAGE, ignore_errors=True)
    bp.OUT = STAGE
    bp.build()

    out = bk.out
    # Only this book's output is cleared. Wiping all of docs/ would delete the
    # other books, which is exactly the kind of thing a library must not do.
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(os.path.join(out, "assets"), exist_ok=True)

    if bk.has("math"):
        library.write(os.path.join(out, "assets", "katex.min.css"),
                      library.read(os.path.join(VEND, "katex.min.css")))
        shutil.copytree(os.path.join(VEND, "fonts"), os.path.join(out, "assets", "fonts"))
    shutil.copy(os.path.join(library.ASSETS, "book.css"), os.path.join(out, "assets"))
    library.write(os.path.join(out, "assets", "book.js"), runtime_js())

    n = 0
    stats = {"words": 0, "eq": 0, "boxes": 0, "planned": len(bp.FLAT)}

    async def render(src, title, desc, sbhead, wide, extra, dest,
                     count_into_stats=False):
        pg = await browser.new_page(viewport={"width": 1280, "height": 1000})
        await pg.goto("file://" + src)
        await pg.wait_for_timeout(2400)
        # Rewind any animated figure before the DOM is saved, so two builds of
        # identical source produce identical files.
        await pg.evaluate("() => { if (window.NMT && NMT.resetForSnapshot) NMT.resetForSnapshot(); }")
        await pg.wait_for_timeout(60)
        body = await pg.evaluate("document.querySelector('.main .col').innerHTML")
        words = await pg.evaluate(WORDCOUNT_JS)
        toc = await pg.evaluate("document.getElementById('sb-toc').innerHTML")
        await pg.close()
        body = body.replace('href="chapters/', 'href="')
        if count_into_stats:
            stats["words"] += words
            stats["eq"] += len(re.findall(r'class="katex"', body))
            stats["boxes"] += len(re.findall(r'class="callout plain"', body))
        library.write(dest, SHELL.format(mathcss=mathcss(bk), title=title, desc=html.escape(desc), nav=nav(bk),
                                         sbhead=sbhead, toc=toc, body=body,
                                         wide=wide, extra=extra,
                                         book=html.escape(bk.title)))

    for num, slug, title, part, _m in bp.FLAT:
        src = os.path.join(STAGE, "chapters", slug + ".html")
        if not os.path.exists(src):
            continue
        raw = library.read(bk.chapter_path(slug))
        m = re.search(r"<!--SCRIPT-->(.*?)<!--/SCRIPT-->", raw, re.S)
        extra = "<script>\n" + m.group(1) + "\n</script>" if m else ""
        await render(src, f"{num} {title}",
                     f"Chapter {num} of {bk.title}: {title}.",
                     f"Ch {num}", "", extra, os.path.join(out, slug + ".html"),
                     count_into_stats=True)
        n += 1

    pages = [("index", "contents", "Parts", f"Every chapter of {bk.title}.")]
    if bk.has("ledger"):
        pages.append(("ledger", "ledger", "Ledger",
                      "Every mathematical object in the book: where it was defined, "
                      "what for, and where it is spent."))
    if bk.has("throughline"):
        pages.append(("throughline", "throughline", "Through-Line",
                      "The whole book in plain language, with no mathematics."))
    for name, outname, sbhead, desc in pages:
        src = os.path.join(STAGE, name + ".html")
        if os.path.exists(src):
            t = {"index": "Chapters", "ledger": "Math Ledger",
                 "throughline": "In Plain Terms"}[name]
            await render(src, t, desc, sbhead, " wide", "",
                         os.path.join(out, outname + ".html"))

    def human(x):
        return f"{x/1000:.0f}k" if x >= 10000 else f"{x:,}"
    landing_page(bk, {"CH": f"{n} / {stats['planned']}", "WORDS": human(stats["words"]),
                      "EQ": human(stats["eq"]), "BOXES": str(stats["boxes"])})
    return n, stats


async def main():
    os.makedirs(DOCS, exist_ok=True)
    library.write(os.path.join(DOCS, ".nojekyll"), "")

    results = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        for bk in library.books():
            n, stats = await build_book(bk, browser)
            results.append((bk, n, stats))
            print(f"  {bk.slug}: {n}/{stats['planned']} chapters, "
                  f"{stats['words']:,} words, {stats['eq']:,} expressions")
        await browser.close()
    shutil.rmtree(STAGE, ignore_errors=True)

    hub(results)

    tot = sum(os.path.getsize(os.path.join(dp, f))
              for dp, _, fs in os.walk(DOCS) for f in fs)
    built = sum(n for _b, n, _s in results)
    print(f"docs/: library hub + {len(results)} books, {built} chapters ({tot/1e6:.1f} MB)")


if __name__ == "__main__":
    asyncio.run(main())
