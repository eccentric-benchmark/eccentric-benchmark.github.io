# eccentric-benchmark.github.io

The website of [ECCentric](https://github.com/TUM-DSE/eccentric), a benchmark of quantum error correction codes
on realistic hardware: <https://eccentric-benchmark.github.io>. Plain HTML served by GitHub Pages; no framework.

## Pages

| Page | What it shows | Built from |
| --- | --- | --- |
| `index.html` | A current finding, the effort, the pipeline, featured findings, citation | `figures/manifest.json`, `data/effort.json`, `data/codes.json`, `data/devices.json`, `data/sweep.json` |
| `results/findings.html` | Every figure with its finding, caption, data and a link into the Explorer | `figures/` |
| `results/explorer.html` | Every result, filterable; the address keeps the filters (`?code=surface&backend=real_willow&best=1`) | `data/sweep.json`, loaded in the browser |
| `results/codes.html`, `results/devices.html` | Each code's circuit, each device's couplers and noise | `data/codes.json`, `data/devices.json`, `data/labels.json` |
| `results/decoders.html` | How often each decoder is as good as the best, its speed, by code family | `data/sweep.json`, `figures/decoders.*`, `data/decoders-info.json` |
| `method.html` | How a result is made, stage by stage | `data/` |
| `paper.html` | The paper: links, abstract, citation, authors | |

The other `.html` files at the old addresses (`overview.html`, `scope.html`, the paper's old results pages, ...) redirect to their new places.

## Where the content comes from

- `figures/` is copied from ECCentric's `site/figures` (`python -m eccentric.figures`) by the
  *sync figures from ECCentric* workflow on the 1st and 15th of each month.
- `data/sweep.json`, `data/codes.json`, `data/devices.json` and `data/effort.json` are ECCentric's website exports.
- `data/decoders-info.json` describes the decoders, condensed from ECCentric's `docs/decoders.md`; edit it when that
  file changes.

## Build

Parts of the pages are generated between marker comments (`<!-- gen:... -->`, `<!-- shell:... -->`,
`<!-- n:... -->`): the navigation, the footer, and everything drawn from the data. After changing data, figures or
a page's shell, run

```bash
python3 tools/build.py          # standard library only
```

and commit the result. The *build pages* workflow runs it on every push to `main` that touches data, figures or
pages, and commits what changed, so forgetting it only delays the update. The navigation and the generated blocks
are defined in `tools/build.py`; the styles are `assets/css/site.css`, the shared script `assets/js/site.js`.

To preview locally:

```bash
python3 -m http.server 8000     # then open http://localhost:8000
```
