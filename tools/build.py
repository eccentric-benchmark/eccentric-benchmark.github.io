#!/usr/bin/env python3
"""Fill in the generated parts of the site from its data. Standard library only; run from anywhere:

    python3 tools/build.py

Pages are plain HTML. Between marker comments, this script writes:

    <!-- shell:head --> ... <!-- /shell:head -->        fonts, stylesheet, favicon, link-preview tags
    <!-- shell:header --> ... <!-- /shell:header -->    the navigation bar, with the page's item marked
    <!-- shell:footer --> ... <!-- /shell:footer -->    the footer and site.js
    <!-- gen:NAME --> ... <!-- /gen:NAME -->            content built from data/ and figures/ (see GENERATORS)
    <!-- n:KEY -->...<!-- /n:KEY -->                     a single number from data/effort.json

Everything else in a page is edited by hand. The script also writes data/labels.json (the display names of the
sweep's devices, noise models, decoders and operations, for pages that do not load the whole sweep) and the
redirect pages of REDIRECTS. It runs in the GitHub workflows after figures or data change; run it locally after
editing a page's shell or the data, and commit the result.
"""
import collections
import html
import json
import math
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = "https://eccentric-benchmark.github.io/"

NAV = [
    ("method", "Method", "method.html"),
    ("findings", "Findings", "results/findings.html"),
    ("explorer", "Explorer", "results/explorer.html"),
    ("codes", "Codes", "results/codes.html"),
    ("devices", "Devices", "results/devices.html"),
    ("decoders", "Decoders", "results/decoders.html"),
    ("paper", "Paper", "paper.html"),
]

# Page -> the navigation item it belongs to
PAGES = {
    "index.html": None,
    "method.html": "method",
    "paper.html": "paper",
    "contact.html": None,
    "results/findings.html": "findings",
    "results/explorer.html": "explorer",
    "results/codes.html": "codes",
    "results/devices.html": "devices",
    "results/decoders.html": "decoders",
}

# Old addresses, kept working
REDIRECTS = {
    "overview.html": "method.html",
    "scope.html": "method.html#codes",
    "methodology.html": "method.html#statistics",
    "results/compiler_overhead.html": "results/findings.html#translation",
    "results/connectivity.html": "results/findings.html#topology",
    "results/hardware.html": "results/findings.html#technologies",
    "results/intra_vs_dist.html": "results/findings.html#distributed",
    "results/hardware_restrictions.html": "paper.html",
    "results/framework_analysis.html": "paper.html",
    "results/qec_analysis.html": "paper.html",
}

# Where in the Explorer the results behind each figure are (query string), or another page
EXPLORE = {
    "where-codes-work": "results/explorer.html?operation=memory&basis=Z&best=1",
    "routing-vs-native": "results/explorer.html?slice=bb_native",
    "below-threshold": "results/explorer.html?slice=noise_scaling",
    "decoders": "results/decoders.html",
    "x-vs-z": "results/explorer.html?slice=basis_x",
    "willow": "results/explorer.html?slice=willow_surface",
    "topology": "results/explorer.html?slice=paper_topology&error_type=modsi1000",
    "technologies": "results/explorer.html?slice=paper_topology",
    "distributed": "results/explorer.html?slice=paper_dqc",
}
HERO_FIGURE = "where-codes-work"

TAXONOMY_ORDER = ["Topological", "QLDPC", "Floquet", "Subsystem", "Concatenated", "Algebraic", "Hybrid"]
TAXONOMY_TEXT = {
    "Topological": "Information stored in global features of a lattice, robust against local errors; the distance grows with the lattice.",
    "QLDPC": "Sparse checks that keep a constant encoding rate as the distance grows, at the price of long-range connections.",
    "Floquet": "Codes whose checks are two-qubit measurements in a repeating schedule, so the circuit needs no ancillas.",
    "Subsystem": "Stabilizer codes that encode into a subsystem, using gauge qubits to simplify syndrome extraction.",
    "Concatenated": "One code nested inside another, level by level.",
    "Algebraic": "Codes built from classical algebraic codes, such as the CSS code of the classical Golay code.",
    "Hybrid": "Codes designed around one device's connectivity, such as IBM's heavy-hex lattice.",
}
MAKER_ORDER = ["IBM", "Google", "Quantinuum", "Infleqtion", "Harvard/MIT", "Synthetic"]
DECODER_KIND_ORDER = ["Search", "Matching", "Hypergraph matching", "Belief propagation", "Color code", "Concatenated", "Union-find"]
WITH_RATE = {"measured", "low statistics", "upper bound"}
CONFIG_KEY = ["slice", "code", "schedule", "basis", "operation", "distance", "rounds", "backend", "error_type", "error_probability"]
# Sequential blue, light to dark (100 ... 700): the share of configurations where a decoder is as good as the best
RAMP = ["#cce3fd", "#9dc8f7", "#6aabf1", "#338ced", "#2370cd", "#1757ac", "#0e3d7e"]

BIBTEX = r"""@article{10.1145/3805635,
  author    = {\'{S}wierkowska, Aleksandra and Pflieger, Jannik and Giortamis, Emmanouil and Bhatotia, Pramod},
  title     = {ECCentric: An Empirical Analysis of Quantum Error Correction Codes},
  journal   = {Proc. ACM Meas. Anal. Comput. Syst.},
  year      = {2026},
  volume    = {10},
  number    = {2},
  articleno = {37},
  numpages  = {33},
  month     = may,
  publisher = {Association for Computing Machinery},
  doi       = {10.1145/3805635},
  url       = {https://doi.org/10.1145/3805635}
}"""

e = html.escape


def load(path):
    with open(ROOT / path, encoding="utf-8") as f:
        return json.load(f)


def at_least(n):
    """Every figure rounded down to two significant digits"""
    if n >= 1e9:
        return f"{math.floor(n / 1e8) / 10:g} billion"
    if n >= 1e6:
        return f"{math.floor(n / 1e6):,} million"
    step = 10 ** max(0, int(math.floor(math.log10(n))) - 1)
    return f"{(n // step) * step:,}+"


class Data:
    def __init__(self):
        self.effort = load("data/effort.json")
        self.manifest = load("figures/manifest.json")
        self.figures = {f["id"]: f for f in self.manifest["figures"]}
        self.codes = load("data/codes.json")["codes"]
        self.devices = load("data/devices.json")["devices"]
        self.decoder_info = load("data/decoders-info.json")["decoders"]
        sweep = load("data/sweep.json")
        self.labels = sweep["labels"]
        cols = sweep["columns"]
        self.rows = [dict(zip(cols, r)) for r in sweep["rows"]]
        self.decoder_times = {}
        with open(ROOT / "figures/decoders.csv", encoding="utf-8") as f:
            head = f.readline().strip().split(",")
            for line in f:
                r = dict(zip(head, line.strip().split(",")))
                self.decoder_times[r["decoder"]] = float(r["median_ms_per_shot"])
        self.decoder_stats = self._decoder_stats()

    def _decoder_stats(self):
        """Per decoder: coverage, and how often it is as good as the best decoder (the rule of the decoders figure:
        configurations with at least three decoders and a best logical error rate below 0.4; a decoder is good
        enough when the low end of its 95% interval reaches the best decoder's high end)"""
        stats = collections.defaultdict(lambda: {"results": 0, "codes": set(), "na": 0, "timeouts": 0, "compared": 0, "good": 0,
                                                 "by_tax": collections.defaultdict(lambda: [0, 0])})
        groups = collections.defaultdict(list)
        for r in self.rows:
            s = stats[r["decoder"]]
            if r["status"] in WITH_RATE:
                s["results"] += 1
                s["codes"].add(r["code"])
                groups[tuple(r[k] for k in CONFIG_KEY)].append(r)
            elif r["status"] == "decoder not applicable":
                s["na"] += 1
            elif r["status"] == "timeout":
                s["timeouts"] += 1
        self.compared_configs = 0
        for rs in groups.values():
            if len({r["decoder"] for r in rs}) < 3:
                continue
            rates = [r["logical_error_rate"] for r in rs if r["logical_error_rate"] is not None]
            if rates and min(rates) >= 0.4:
                continue
            best_high = min(r["ler_high"] for r in rs if r["ler_high"] is not None)
            self.compared_configs += 1
            for r in rs:
                good = (r["ler_low"] or 0.0) <= best_high
                s = stats[r["decoder"]]
                s["compared"] += 1
                s["good"] += good
                t = s["by_tax"][r["taxonomy"]]
                t[0] += 1
                t[1] += good
        return stats


# ---------------------------------------------------------------- shell

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&amp;'
         'family=IBM+Plex+Sans:wght@400;500;600&amp;display=swap" rel="stylesheet">')

LOGO = ('<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="1" y="1" width="22" height="22" rx="4" fill="#0f62fe"/>'
        '<g fill="#fff"><circle cx="7" cy="7" r="2"/><circle cx="17" cy="7" r="2"/><circle cx="7" cy="17" r="2"/>'
        '<circle cx="17" cy="17" r="2"/></g><circle cx="12" cy="12" r="2.4" fill="#a6c8ff"/></svg>')


def shell_head(page, text, p):
    title = re.search(r"<title>(.*?)</title>", text, re.S)
    desc = re.search(r'<meta name="description" content="(.*?)">', text, re.S)
    title = title.group(1).strip() if title else "ECCentric"
    desc = desc.group(1).strip() if desc else ""
    url = SITE + ("" if page == "index.html" else page)
    return "\n".join([
        FONTS,
        f'<link rel="stylesheet" href="{p}assets/css/site.css">',
        f'<link rel="icon" href="{p}assets/favicon.svg" type="image/svg+xml">',
        f'<link rel="canonical" href="{url}">',
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="ECCentric">',
        f'<meta property="og:title" content="{title}">',
        f'<meta property="og:description" content="{desc}">',
        f'<meta property="og:url" content="{url}">',
        f'<meta property="og:image" content="{SITE}figures/{HERO_FIGURE}.png">',
        '<meta name="twitter:card" content="summary_large_image">',
    ])


def shell_header(page, p):
    active = PAGES.get(page)
    current = ' aria-current="page"'
    items = "\n".join(
        f'<li><a href="{p}{href}"{current if key == active else ""}>{label}</a></li>'
        for key, label, href in NAV)
    return (f'<a class="skip-link" href="#main">Skip to content</a>\n'
            f'<header class="site-header">\n<div class="wrap header-inner">\n'
            f'<a class="brand" href="{p}index.html">{LOGO} ECCentric</a>\n'
            f'<nav class="site-nav" aria-label="Main">\n<ul>\n{items}\n</ul>\n</nav>\n</div>\n</header>')


def shell_footer(page, p):
    return (f'<footer class="site-footer">\n<div class="wrap footer-inner">\n<div class="footer-about">\n'
            f'<a href="https://www.munich-quantum-valley.de/"><img src="{p}images/mqv.png" alt="Munich Quantum Valley" width="109" height="44"></a>\n'
            f'<p>ECCentric is developed by the <a href="https://dse.in.tum.de/">Systems Research Group</a> at the Technical '
            f'University of Munich, supported by Munich Quantum Valley.</p>\n</div>\n'
            f'<ul class="footer-links">\n'
            f'<li><a href="{p}paper.html">Paper</a></li>\n'
            f'<li><a href="https://github.com/TUM-DSE/eccentric">Code on GitHub</a></li>\n'
            f'<li><a href="{p}contact.html">Contact</a></li>\n'
            f'</ul>\n</div>\n</footer>\n'
            f'<script src="{p}assets/js/site.js" defer></script>')


# ---------------------------------------------------------------- generated blocks


def gen_effort(d, p):
    x = d.effort
    years = x["cpu_hours"] / 8766
    tiles = [
        (at_least(x["results"]), "logical error rates measured"),
        (at_least(x["jobs"]), "simulation jobs run"),
        (at_least(x["cpu_hours"]), "CPU-hours" + (f", over {int(years)} year{'s' if years >= 2 else ''} on one core" if years >= 1 else "")),
        (at_least(x["shots"]), "shots simulated and decoded"),
        (f'{x["codes"]} · {x["devices"]} · {x["noise_models"]} · {x["decoders"]}', "codes · devices · noise models · decoders"),
    ]
    body = "\n".join(f'<div class="tile"><div class="value">{v}</div><div class="name">{e(n)}</div></div>' for v, n in tiles)
    return f'<div class="tiles">\n{body}\n</div>'


def gen_hero(d, p):
    f = d.figures.get(HERO_FIGURE) or next(x for x in d.manifest["figures"] if x["group"] == "featured")
    return (f'<figure class="hero-figure">\n<a href="{p}results/findings.html#{f["id"]}">'
            f'<img src="{p}figures/{f["files"]["svg"]}" alt="{e(f["title"])}. {e(f["finding"])}" width="900" height="600"></a>\n'
            f'<figcaption>One of ECCentric\'s results: {e(f["title"][0].lower() + f["title"][1:])}. '
            f'<a href="{p}results/findings.html#{f["id"]}">About this figure</a></figcaption>\n</figure>')


def figure_links(f, p, csv=True):
    links = []
    target = EXPLORE.get(f["id"])
    if target:
        name = "Decoders page" if target.endswith("decoders.html") else "Explore these results"
        links.append(f'<a class="arrow" href="{p}{target}">{name}</a>')
    if csv:
        links.append(f'<a href="{p}figures/{f["files"]["csv"]}" download>Data (CSV)</a>')
        links.append(f'<a href="{p}figures/{f["files"]["png"]}">PNG</a>')
        links.append(f'<a href="{p}figures/{f["files"]["svg"]}">SVG</a>')
    return links


def gen_featured(d, p):
    cards = []
    for f in d.manifest["figures"]:
        if f["group"] != "featured" or f["id"] == HERO_FIGURE:
            continue
        links = [f'<a class="arrow" href="{p}results/findings.html#{f["id"]}">Figure and data</a>'] + figure_links(f, p, csv=False)
        cards.append(
            f'<article class="card">\n<a class="card-media" href="{p}results/findings.html#{f["id"]}" tabindex="-1" aria-hidden="true">'
            f'<img src="{p}figures/{f["files"]["svg"]}" alt="" loading="lazy"></a>\n'
            f'<div class="card-body">\n<h3>{e(f["title"])}</h3>\n<p>{e(f["finding"])}</p>\n'
            f'<p class="link-row">{" ".join(links)}</p>\n</div>\n</article>')
    return '<div class="cards">\n' + "\n".join(cards) + "\n</div>"


def gen_findings_toc(d, p):
    names = {"featured": "Featured", "benchmark": "Paper experiment"}
    items = "\n".join(f'<li><span class="group">{names.get(f["group"], f["group"])}</span><a href="#{f["id"]}">{e(f["title"])}</a></li>'
                      for f in d.manifest["figures"])
    return f'<ul class="toc">\n{items}\n</ul>'


def gen_findings(group):
    def gen(d, p):
        blocks = []
        for f in d.manifest["figures"]:
            if f["group"] != group:
                continue
            links = figure_links(f, "../")
            blocks.append(
                f'<section class="fig" id="{f["id"]}">\n<h3>{e(f["title"])}</h3>\n<p class="finding">{e(f["finding"])}</p>\n'
                f'<img src="../figures/{f["files"]["svg"]}" alt="{e(f["title"])}. {e(f["finding"])}" loading="lazy">\n'
                f'<p class="caption">{e(f["caption"])}</p>\n<p class="link-row">{" ".join(links)}</p>\n</section>')
        return "\n".join(blocks)
    return gen


def gen_bibtex(d, p):
    return f'<div class="copy-wrap"><pre class="bibtex">{e(BIBTEX)}</pre></div>'


# ---------------- pipeline diagram


def _stage(i, key, name, count, href, pop_html, out=False):
    return (f'<li class="stage{" stage-out" if out else ""}" id="stage-{key}">\n'
            f'<a class="stage-card" href="{href}"><span class="stage-step">{i:02d}</span>'
            f'<span class="stage-name">{name}</span><span class="stage-count">{count}</span></a>\n'
            f'<button class="stage-toggle" type="button" aria-expanded="false" aria-controls="pop-{key}" '
            f'aria-label="List of {name.lower()}" hidden>&#9662;</button>\n'
            f'<div class="stage-pop" id="pop-{key}"><div class="stage-pop-inner">\n{pop_html}\n</div></div>\n</li>')


def gen_pipeline(d, p):
    x = d.effort
    sweep_codes = {r["code"] for r in d.rows if r["status"] in WITH_RATE}
    # Codes: families by taxonomy, each linking to its first code with results
    fams = families_with_results(d, sweep_codes)
    parts = ['<p>Every code family with results. Pick one to see its circuit and results.</p><dl>']
    for tax, families in fams.items():
        links = [f'<a href="{p}results/codes.html?code={e(cs[0]["id"])}">{e(fam)}</a>' for fam, cs in families.items()]
        parts.append(f'<dt>{e(tax)}</dt><dd>{", ".join(links)}</dd>')
    parts.append(f'</dl><a class="pop-more arrow" href="{p}results/codes.html">All codes</a>')
    n_fam = sum(len(f) for f in fams.values())
    stages = [_stage(1, "codes", "Code", f'{x["codes"]} codes in {n_fam} families', f"{p}results/codes.html", "".join(parts))]

    ops = d.labels["operations"]
    op_links = ", ".join(f'<a href="{p}results/explorer.html?operation={k}">{e(v)}</a>' for k, v in ops.items())
    stages.append(_stage(2, "operations", "Operation", "Memory, lattice surgery, logical gates",
                         f"{p}results/explorer.html?operation=memory",
                         f'<p>What the circuit does with the encoded qubits, in the Z or X basis.</p><dl><dt>Operations</dt><dd>{op_links}</dd></dl>'
                         f'<a class="pop-more arrow" href="{p}method.html#operations">How operations are built</a>'))

    by_maker = collections.OrderedDict((m, []) for m in MAKER_ORDER)
    for dev in d.devices:
        by_maker.setdefault(dev["maker"], []).append(dev)
    parts = ['<p>Real and announced devices, projections, and synthetic topologies, each with its couplers and noise.</p><dl>']
    for maker, devs in by_maker.items():
        if devs:
            parts.append(f'<dt>{e(maker)}</dt><dd>' + ", ".join(
                f'<a href="{p}results/devices.html?device={e(v["id"])}">{e(v["label"])}</a>' for v in devs) + "</dd>")
    parts.append(f'<dt>Built for the code</dt><dd><a href="{p}results/explorer.html?backend=native">Native layouts</a>: a coupler for every pair of qubits the circuit entangles</dd>')
    parts.append(f'</dl><a class="pop-more arrow" href="{p}results/devices.html">All devices</a>')
    stages.append(_stage(3, "devices", "Device", f'{x["devices"]} devices from {len([m for m in by_maker if by_maker[m]])} makers',
                         f"{p}results/devices.html", "".join(parts)))

    stages.append(_stage(4, "compile", "Compilation", "Layout, routing, gate translation", f"{p}method.html#compilation",
                         '<p>The circuit is fitted to the device: qubits placed, SWAPs added where qubits are not coupled, '
                         'gates translated to the native gate set.</p><dl>'
                         '<dt>Layout</dt><dd>Qiskit: trivial, dense, SABRE</dd>'
                         '<dt>Routing</dt><dd>Qiskit: basic, SABRE, stochastic, lookahead</dd>'
                         '<dt>Translation</dt><dd>Qiskit, BQSKit or TKET</dd>'
                         f'<dt>What it costs</dt><dd><a href="{p}results/findings.html#routing">Routing overhead</a>, '
                         f'<a href="{p}results/findings.html#translation">translation overhead</a>, '
                         f'<a href="{p}results/findings.html#routing-vs-native">routing vs native layout</a></dd></dl>'
                         f'<a class="pop-more arrow" href="{p}method.html#compilation">How compilation works</a>'))

    noise = d.labels["noise"]
    base = {k: v for k, v in noise.items() if not re.search(r"_x[\d.]+$", k)}
    scaled = sorted({k.rsplit("_x", 1)[0] for k in noise if re.search(r"_x[\d.]+$", k)})
    hardware = [k for k in base if k.startswith("real_")]
    circuit = [k for k in base if not k.startswith("real_")]
    link = lambda k: f'<a href="{p}results/explorer.html?error_type={e(k)}">{e(noise[k])}</a>'
    parts = ['<p>Noise added gate by gate: gate, readout, idle and leakage errors, decay while qubits wait, shuttling and atom loss.</p><dl>',
             f'<dt>Hardware models</dt><dd>{", ".join(link(k) for k in hardware)}</dd>',
             f'<dt>Circuit-level models</dt><dd>{", ".join(link(k) for k in circuit)}</dd>']
    if scaled:
        parts.append(f'<dt>Scaled down</dt><dd>{", ".join(e(noise[k]) for k in scaled if k in noise)}, each at ×0.1, ×0.25 and ×0.5 '
                     f'(<a href="{p}results/explorer.html?slice=noise_scaling">results</a>)</dd>')
    parts.append(f'</dl><a class="pop-more arrow" href="{p}method.html#noise">How noise is modelled</a>')
    stages.append(_stage(5, "noise", "Noise", f'{x["noise_models"]} noise models', f"{p}method.html#noise", "".join(parts)))

    info = {i["id"]: i for i in d.decoder_info}
    used = [k for k in d.labels["decoders"] if d.decoder_stats[k]["results"] > 0]
    by_kind = collections.OrderedDict((k, []) for k in DECODER_KIND_ORDER)
    for k in used:
        by_kind.setdefault(info.get(k, {}).get("kind", "Other"), []).append(k)
    parts = ['<p>Every syndrome is decoded by every decoder that applies to the code.</p><dl>']
    for kind, ks in by_kind.items():
        if ks:
            parts.append(f'<dt>{e(kind)}</dt><dd>' + ", ".join(
                f'<a href="{p}results/decoders.html#{k}">{e(d.labels["decoders"][k])}</a>' for k in ks) + "</dd>")
    parts.append(f'<dt>On the GPU</dt><dd><a href="{p}results/decoders.html#gpu">GPU versions and NVIDIA\'s TCBP-JOBS</a> (separate runs)</dd>')
    parts.append(f'</dl><a class="pop-more arrow" href="{p}results/decoders.html">Compare the decoders</a>')
    stages.append(_stage(6, "decoders", "Decoder", f'{x["decoders"]} decoders', f"{p}results/decoders.html", "".join(parts)))

    stages.append(_stage(7, "results", "Logical error rate", f'{x["results"]:,} results', f"{p}results/explorer.html",
                         '<p>Each result: the logical error rate with its 95% interval, per round, and the shots, SWAPs and gates '
                         'behind it.</p><dl>'
                         f'<dt>Read them</dt><dd><a href="{p}results/findings.html">Findings</a>: what the results show, figure by figure</dd>'
                         f'<dt>Filter them</dt><dd><a href="{p}results/explorer.html">Explorer</a>: every result, filterable and downloadable</dd>'
                         f'<dt>How they are measured</dt><dd><a href="{p}method.html#statistics">Shots, intervals and statuses</a></dd></dl>',
                         out=True))
    return '<ol class="pipeline">\n' + "\n".join(stages) + '\n</ol>'


# ---------------- decoders page


def pct(share):
    """A share as a percentage: whole numbers, but never rounded to 0% or 100% when it is neither"""
    v = 100 * share
    if 0 < v < 0.5 or 99.5 <= v < 100:
        return f"{v:.1f}%"
    return f"{v:.0f}%"


def ramp(share):
    i = min(len(RAMP) - 1, int(share * len(RAMP)))
    return RAMP[i], ("#fff" if i >= 4 else "#161616")


def gen_decoders_figure(d, p):
    f = d.figures.get("decoders")
    if not f:
        return ""
    return (f'<figure class="fig" id="figure" style="border-top:0;padding-top:0;margin-top:0">\n<p class="finding">{e(f["finding"])}</p>\n'
            f'<img src="../figures/{f["files"]["svg"]}" alt="{e(f["title"])}. {e(f["finding"])}" loading="lazy">\n'
            f'<figcaption class="caption">{e(f["caption"])}</figcaption>\n'
            f'<p class="link-row"><a href="../figures/{f["files"]["csv"]}" download>Data (CSV)</a> '
            f'<a href="../figures/{f["files"]["png"]}">PNG</a> <a href="../figures/{f["files"]["svg"]}">SVG</a></p>\n</figure>')


def _decoders_in_order(d):
    used = [k for k in d.labels["decoders"] if d.decoder_stats[k]["results"] > 0]
    return sorted(used, key=lambda k: -(d.decoder_stats[k]["good"] / d.decoder_stats[k]["compared"]) if d.decoder_stats[k]["compared"] else 1)


def gen_decoders_table(d, p):
    info = {i["id"]: i for i in d.decoder_info}
    rows = []
    for k in _decoders_in_order(d):
        s = d.decoder_stats[k]
        share = s["good"] / s["compared"] if s["compared"] else None
        t = d.decoder_times.get(k)
        good = (f'<td class="num" data-value="{share * 100:.2f}"><span class="bar-cell">{pct(share)}'
                f'<span class="bar" aria-hidden="true"><span style="width:{share * 100:.1f}%"></span></span></span></td>'
                if share is not None else '<td class="num" data-value="">–</td>')
        rows.append(
            f'<tr><td><a href="#{k}">{e(d.labels["decoders"][k])}</a></td><td>{e(info.get(k, {}).get("kind", ""))}</td>'
            f'{good}<td class="num" data-value="{s["compared"]}">{s["compared"]:,}</td>'
            f'<td class="num" data-value="{t if t is not None else ""}">{_ms(t)}</td>'
            f'<td class="num" data-value="{s["results"]}">{s["results"]:,}</td>'
            f'<td class="num" data-value="{len(s["codes"])}">{len(s["codes"])}</td>'
            f'<td class="num" data-value="{s["na"]}">{s["na"]:,}</td></tr>')
    head = ('<tr><th data-sort="text" scope="col">Decoder</th><th data-sort="text" scope="col">Kind</th>'
            '<th data-sort="num" class="num" scope="col" aria-sort="descending">As good as the best</th>'
            '<th data-sort="num" class="num" scope="col">Configurations compared</th>'
            '<th data-sort="num" class="num" scope="col">Median time per shot</th>'
            '<th data-sort="num" class="num" scope="col">Results</th><th data-sort="num" class="num" scope="col">Codes</th>'
            '<th data-sort="num" class="num" scope="col">Not applicable</th></tr>')
    return f'<div class="table-wrap"><table class="data" id="decoder-table"><thead>{head}</thead><tbody>\n' + "\n".join(rows) + "\n</tbody></table></div>"


def _ms(t):
    if t is None:
        return "–"
    if t >= 10:
        return f"{t:,.0f} ms"
    if t >= 1:
        return f"{t:.1f} ms"
    us = t * 1000
    return f"{us:.1f} µs" if us < 10 else f"{us:.0f} µs"


def gen_decoders_heat(d, p, minimum=20):
    taxes = [t for t in TAXONOMY_ORDER if any(d.decoder_stats[k]["by_tax"].get(t, [0])[0] for k in d.decoder_stats)]
    head = '<tr><th scope="col"><span class="visually-hidden">Decoder</span></th>' + "".join(f'<th scope="col">{e(t)}</th>' for t in taxes) + "</tr>"
    rows = []
    for k in _decoders_in_order(d):
        s = d.decoder_stats[k]
        if not s["compared"]:
            continue
        cells = []
        for t in taxes:
            n, g = s["by_tax"].get(t, [0, 0])
            if n < minimum:
                cells.append(f'<td class="empty" title="{n} configurations: too few to compare">·</td>')
                continue
            bg, fg = ramp(g / n)
            cells.append(f'<td style="background:{bg};color:{fg}" title="{e(d.labels["decoders"][k])} on {e(t)} codes: as good as the best on '
                         f'{g:,} of {n:,} configurations">{pct(g / n)}</td>')
        rows.append(f'<tr><th scope="row"><a href="#{k}">{e(d.labels["decoders"][k])}</a></th>{"".join(cells)}</tr>')
    legend = "".join(f'<span style="background:{c}"></span>' for c in RAMP)
    return (f'<div class="table-wrap" style="border:0"><table class="heat"><thead>{head}</thead><tbody>\n' + "\n".join(rows) +
            f'\n</tbody></table></div>\n<p class="heat-legend">0% <span class="ramp" aria-hidden="true">{legend}</span> 100% of '
            f'configurations where the decoder is as good as the best. · marks fewer than {minimum} configurations.</p>')


def gen_decoders_cards(d, p):
    info = {i["id"]: i for i in d.decoder_info}
    cards = []
    for k in _decoders_in_order(d):
        s, i = d.decoder_stats[k], info.get(k, {})
        share = f'{pct(s["good"] / s["compared"])} of {s["compared"]:,} configurations' if s["compared"] else "not compared (too few configurations with other decoders)"
        refs = " · ".join(f'<a href="{e(u)}">{e(t)}</a>' for t, u in i.get("links", []))
        t = d.decoder_times.get(k)
        cards.append(
            f'<article class="decoder" id="{k}">\n<span class="kind">{e(i.get("kind", ""))}</span>\n<h3>{e(d.labels["decoders"][k])}</h3>\n'
            f'<p>{e(i.get("description", ""))}</p>\n<dl>\n<dt>Applies to</dt><dd>{e(i.get("applies", ""))}</dd>\n'
            f'<dt>As good as the best</dt><dd>{share}</dd>\n'
            + (f'<dt>Median time per shot</dt><dd>{_ms(t)}</dd>\n' if t is not None else "") +
            f'<dt>Results</dt><dd>{s["results"]:,} on {len(s["codes"])} codes'
            + (f', {s["timeouts"]:,} timed out' if s["timeouts"] else "") + "</dd>\n"
            + (f'<dt>Reference</dt><dd>{refs}</dd>\n' if refs else "") +
            f'</dl>\n<p class="link-row"><a class="arrow" href="explorer.html?decoder={k}">Its results in the Explorer</a></p>\n</article>')
    return '<div class="decoder-list">\n' + "\n".join(cards) + "\n</div>"


def gen_decoders_count(d, p):
    return f"{d.compared_configs:,}"


# ---------------- method page


def families_with_results(d, sweep_codes):
    """Taxonomy -> family -> codes, for the codes with at least one result"""
    fams = collections.OrderedDict()
    for c in sorted(d.codes, key=lambda c: (TAXONOMY_ORDER.index(c["taxonomy"]) if c["taxonomy"] in TAXONOMY_ORDER else 99, c["family"])):
        if c["id"] in sweep_codes:
            fams.setdefault(c["taxonomy"], collections.OrderedDict()).setdefault(c["family"], []).append(c)
    return fams


def gen_families(d, p):
    sweep_codes = {r["code"] for r in d.rows if r["status"] in WITH_RATE}
    rows = []
    for tax, families in families_with_results(d, sweep_codes).items():
        links = [f'<a href="{p}results/codes.html?code={e(cs[0]["id"])}">{e(fam)}</a> ({len(cs)})' for fam, cs in families.items()]
        n = sum(len(cs) for cs in families.values())
        rows.append(f'<tr><td>{e(tax)}</td><td>{e(TAXONOMY_TEXT.get(tax, ""))}</td><td>{", ".join(links)}</td><td class="num">{n}</td></tr>')
    return ('<div class="table-wrap"><table class="families"><thead><tr><th scope="col">Taxonomy</th><th scope="col">Idea</th>'
            '<th scope="col">Families (codes with results)</th><th scope="col" class="num">Codes</th></tr></thead><tbody>\n'
            + "\n".join(rows) + "\n</tbody></table></div>")


GENERATORS = {
    "effort": gen_effort,
    "hero": gen_hero,
    "featured": gen_featured,
    "pipeline": gen_pipeline,
    "bibtex": gen_bibtex,
    "findings-toc": gen_findings_toc,
    "findings-featured": gen_findings("featured"),
    "findings-benchmark": gen_findings("benchmark"),
    "decoders-figure": gen_decoders_figure,
    "decoders-table": gen_decoders_table,
    "decoders-heat": gen_decoders_heat,
    "decoders-cards": gen_decoders_cards,
    "decoders-count": gen_decoders_count,
    "families": gen_families,
}


def replace_block(text, kind, name, content, page):
    pattern = re.compile(rf"(<!-- {kind}:{re.escape(name)} -->).*?(<!-- /{kind}:{re.escape(name)} -->)", re.S)
    if not pattern.search(text):
        sys.exit(f"{page}: marker <!-- {kind}:{name} --> not found")
    inline = kind == "n"
    sep = "" if inline else "\n"
    return pattern.sub(lambda m: m.group(1) + sep + content + sep + m.group(2), text)


def build_page(page, d):
    path = ROOT / page
    text = path.read_text(encoding="utf-8")
    p = "../" if "/" in page else ""
    text = replace_block(text, "shell", "head", shell_head(page, text, p), page)
    text = replace_block(text, "shell", "header", shell_header(page, p), page)
    text = replace_block(text, "shell", "footer", shell_footer(page, p), page)
    for name in re.findall(r"<!-- gen:([\w-]+) -->", text):
        if name not in GENERATORS:
            sys.exit(f"{page}: no generator for gen:{name}")
        text = replace_block(text, "gen", name, GENERATORS[name](d, p), page)
    for key in re.findall(r"<!-- n:([\w-]+) -->", text):
        value = d.effort.get(key)
        if value is None:
            sys.exit(f"{page}: data/effort.json has no {key}")
        text = replace_block(text, "n", key, f"{value:,}" if isinstance(value, int) else str(value), page)
    path.write_text(text, encoding="utf-8")


def build_redirect(page, target):
    p = "../" if "/" in page else ""
    url = p + target
    (ROOT / page).write_text(
        f'<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<title>Moved</title>\n'
        f'<meta name="robots" content="noindex">\n<link rel="canonical" href="{SITE}{target}">\n'
        f'<meta http-equiv="refresh" content="0; url={url}">\n</head>\n<body>\n'
        f'<p>This page has moved to <a href="{url}">{target}</a>.</p>\n</body>\n</html>\n', encoding="utf-8")


def main():
    d = Data()
    labels = {k: d.labels[k] for k in ("devices", "noise", "decoders", "operations", "slices")}
    (ROOT / "data/labels.json").write_text(json.dumps(labels, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for page in PAGES:
        build_page(page, d)
    for page, target in REDIRECTS.items():
        build_redirect(page, target)
    print(f"built {len(PAGES)} pages and {len(REDIRECTS)} redirects")


if __name__ == "__main__":
    main()
