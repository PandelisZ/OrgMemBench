# Makefile --- OrgMemBench paper
#
# Detects the available LaTeX engine at run time and degrades gracefully:
#   1. latexmk   (preferred --- handles bibtex + multiple passes itself)
#   2. tectonic  (self-contained; pulls packages on demand)
#   3. pdflatex + bibtex  (classic manual passes)
#   4. none      --> prints a helpful message, exits non-zero
#
# Targets:
#   make / make pdf   build main.pdf
#   make watch        continuous rebuild + preview (latexmk -pvc; else tectonic --watch)
#   make clean        remove LaTeX build cruft (keeps main.pdf)
#   make distclean    also remove main.pdf
#   make engine       print which engine was detected

MAIN     := main
TEX      := $(MAIN).tex
PDF      := $(MAIN).pdf

# Engine detection (evaluated when the recipe runs).
LATEXMK  := $(shell command -v latexmk 2>/dev/null)
TECTONIC := $(shell command -v tectonic 2>/dev/null)
PDFLATEX := $(shell command -v pdflatex 2>/dev/null)
BIBTEX   := $(shell command -v bibtex 2>/dev/null)

.PHONY: all pdf watch clean distclean engine help

all: pdf

pdf: $(TEX) refs.bib
ifneq ($(LATEXMK),)
	@echo ">> building with latexmk"
	latexmk -pdf -interaction=nonstopmode -halt-on-error $(MAIN)
else ifneq ($(TECTONIC),)
	@echo ">> building with tectonic"
	tectonic --keep-logs --synctex $(TEX)
else ifneq ($(PDFLATEX),)
	@echo ">> building with pdflatex + bibtex (manual passes)"
	pdflatex -interaction=nonstopmode -halt-on-error $(MAIN)
ifneq ($(BIBTEX),)
	-bibtex $(MAIN)
	pdflatex -interaction=nonstopmode -halt-on-error $(MAIN)
else
	@echo "!! bibtex not found --- citations will show as [?]. Install a full TeX distribution."
endif
	pdflatex -interaction=nonstopmode -halt-on-error $(MAIN)
else
	@echo "================================================================"
	@echo " No LaTeX engine found (looked for latexmk, tectonic, pdflatex)."
	@echo ""
	@echo " Install one of:"
	@echo "   - tectonic   : brew install tectonic        (self-contained)"
	@echo "   - TeX Live   : brew install --cask mactex    (full, includes latexmk)"
	@echo "   - BasicTeX   : brew install --cask basictex  (then tlmgr install latexmk)"
	@echo ""
	@echo " Then run 'make' again. See ../docs/publishing-a-paper-2026.md section 1.1."
	@echo "================================================================"
	@exit 1
endif

watch: $(TEX) refs.bib
ifneq ($(LATEXMK),)
	@echo ">> watching with latexmk -pvc"
	latexmk -pdf -pvc -interaction=nonstopmode $(MAIN)
else ifneq ($(TECTONIC),)
	@echo ">> watching with tectonic --watch"
	tectonic --watch --keep-logs --synctex $(TEX)
else
	@echo "!! 'make watch' needs latexmk or tectonic. Falling back to a single build:"
	@$(MAKE) pdf
endif

engine:
ifneq ($(LATEXMK),)
	@echo "latexmk: $(LATEXMK)"
else ifneq ($(TECTONIC),)
	@echo "tectonic: $(TECTONIC)"
else ifneq ($(PDFLATEX),)
	@echo "pdflatex: $(PDFLATEX)  (bibtex: $(if $(BIBTEX),$(BIBTEX),NOT FOUND))"
else
	@echo "none --- no LaTeX engine on PATH"
endif

clean:
	rm -f $(MAIN).aux $(MAIN).log $(MAIN).out $(MAIN).bbl $(MAIN).blg \
	      $(MAIN).synctex.gz $(MAIN).fls $(MAIN).fdb_latexmk \
	      $(MAIN).toc $(MAIN).lof $(MAIN).lot $(MAIN).run.xml $(MAIN).bcf
	rm -rf _minted-$(MAIN)

distclean: clean
	rm -f $(PDF)

help:
	@echo "make / make pdf  build $(PDF)"
	@echo "make watch       continuous rebuild + preview"
	@echo "make clean       remove build cruft (keep $(PDF))"
	@echo "make distclean   also remove $(PDF)"
	@echo "make engine      show detected LaTeX engine"
