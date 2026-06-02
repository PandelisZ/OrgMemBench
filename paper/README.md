# OrgMemBench paper

Working title: **"OrgMemBench: A Benchmark for Long-Horizon Organizational
Memory in AI Agents"** (placeholder, confirm before submission).

This directory is a **scaffold**. The body of `main.tex` is lorem-ipsum
placeholder text; every section carries a `% GUIDANCE:` comment paraphrased from
the team's authoritative guide:

> **`../docs/publishing-a-paper-2026.md`** is the authoritative guide.
> The section structure here mirrors its section 5.3 outline; the toolchain
> mirrors its section 5.1; the Datasets-and-Benchmarks requirements (datasheet,
> Croissant, contamination, leaderboard) come from its section 3.2.

Fill in the placeholders; do not restructure without re-reading that guide.

## Build

```bash
make            # build main.pdf (auto-detects the LaTeX engine)
make watch      # continuous rebuild + preview
make clean      # remove build cruft (keeps main.pdf)
make distclean  # also remove main.pdf
make engine     # show which engine was detected
```

`make` auto-detects an engine in this order and degrades gracefully:

1. **latexmk** (preferred --- runs bibtex + multiple passes for you)
2. **tectonic** (self-contained; pulls packages on demand --- recommended local
   engine per the guide section 1.3)
3. **pdflatex + bibtex** (classic manual passes)
4. none --- prints install instructions and exits non-zero

If no engine is installed:

```bash
brew install tectonic            # self-contained, fastest to set up
# or
brew install --cask mactex       # full TeX Live (includes latexmk)
```

## Toolchain assumed

Per `../docs/publishing-a-paper-2026.md` section 5.1:

- **LaTeX**, `booktabs` + `siunitx` for tables, `graphicx` for figures (with alt
  text for arXiv HTML), `natbib` + BibTeX for references.
- **Figures**: matplotlib + SciencePlots (`science` style), exported as PDF.
  See `figures/README.md` for the full list of figures to produce.
- **References**: Zotero 7 -> BibTeX in `refs.bib`. Always include `url`/`doi`.

## Document class is a PLACEHOLDER

`main.tex` uses `\documentclass[11pt]{article}` so it compiles **today** with no
venue style download. **Swap to the venue style when targeting a venue**
(guide section 1.1):

- NeurIPS 2026 -> `neurips_2026.sty`
- ICLR 2026 -> `iclr2026.sty` (double-blind: drop author names at submission)

The top of `main.tex` has a comment block describing exactly what to change.

## File map

```
paper/
├── main.tex      # paper skeleton (placeholder body + GUIDANCE comments)
├── refs.bib      # starter references (real entries + TODO-verify stubs)
├── Makefile      # engine-detecting build
├── README.md     # this file
├── .gitignore    # ignores build cruft + root main.pdf, keeps figures/*.pdf
├── figures/
│   ├── README.md # the 9 figures to produce (guide section 5.2)
│   └── .gitkeep
└── scripts/
    └── make_teaser_placeholder.py   # trivial Fig. 1 placeholder (needs matplotlib)
```

## Checklist before arXiv submission

Copied from `../docs/publishing-a-paper-2026.md` section 5.4. This is the work
left to do; the scaffold only stands up the structure.

**Paper quality**
- [ ] Abstract states problem, gap, contribution, and headline result clearly
- [ ] Contributions list in introduction: 3--5 concrete, verifiable items
- [ ] Teaser figure (Figure 1) is clear at thumbnail size
- [ ] All tables use `booktabs` formatting; no vertical rules
- [ ] All figures have captions that are self-contained
- [ ] Error bars / confidence intervals reported for all main results
- [ ] Statistical significance stated for key comparisons
- [ ] Related work covers all directly competitive benchmarks
- [ ] Limitations section is honest and specific
- [ ] Ethics / broader impact section addresses data sourcing and potential misuse
- [ ] Reproducibility statement links to code, data, and model configs
- [ ] NeurIPS paper checklist completed (if submitting to NeurIPS)
- [ ] LLM use disclosed if applicable
- [ ] Language policy: full English version included

**Code and data**
- [ ] GitHub repo is public with MIT/Apache 2.0 license
- [ ] README has: abstract, quick-start commands, links to all assets
- [ ] CITATION.cff file present
- [ ] `requirements.txt` with exact pinned versions
- [ ] Evaluation script is runnable end-to-end from a clean environment
- [ ] Dataset on Hugging Face Datasets with a dataset card
- [ ] Zenodo upload complete; DOI recorded in paper
- [ ] Croissant metadata file present (from HF auto-generation or mlcroissant)
- [ ] Datasheet for Datasets in appendix

**arXiv submission**
- [ ] LaTeX compiles cleanly on arXiv (test with a fresh TeX Live or Tectonic)
- [ ] HTML preview checked during submission; math and figures render
- [ ] Filenames use only permitted characters (`a-z A-Z 0-9 _ + - . , =`)
- [ ] No empty figures or external-only figure references
- [ ] `.bib` file included (arXiv processes it to `.bbl`)
- [ ] License selected (CC BY 4.0 recommended)
- [ ] Primary category: `cs.CL`; secondary: `cs.AI`, `cs.LG`
- [ ] Endorsement obtained if first submission to this category

**Project page and distribution**
- [ ] GitHub Pages site live with: title, authors, abstract, teaser, links
- [ ] HF Leaderboard Space live with: validation set submission, metrics, rankings
- [ ] X/Twitter thread drafted; teaser figure and result table images ready
- [ ] HF Papers submission ready (paste arXiv URL on launch day)
- [ ] alphaXiv link noted to share alongside arXiv link
