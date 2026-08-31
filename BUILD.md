# Build and validation

Run from the package root.

## Manuscript rendering

```sh
export SOURCE_DATE_EPOCH=1788177600
export FORCE_SOURCE_DATE=1
export TZ=UTC

pandoc paper.md \
  --citeproc \
  --bibliography=references.bib \
  --standalone \
  --from=markdown+tex_math_single_backslash+tex_math_dollars \
  --to=latex \
  --output=paper.tex \
  --variable=geometry:margin=1in \
  --variable=fontsize=11pt \
  --variable=colorlinks=true \
  --variable=linkcolor=blue \
  --variable=urlcolor=blue \
  --variable=documentclass=article \
  --metadata=title-meta:"Structural reductions toward the quartic Hessian conjecture in dimension four" \
  --metadata=author-meta:"Anonymous" \
  --metadata=subject:"Unrefereed computer-assisted structural reductions toward HC4" \
  --metadata=keywords:"Hessian nilpotent polynomial, Jacobian conjecture, binary decimic, computer-assisted proof"

pdflatex -interaction=nonstopmode -halt-on-error paper.tex
pdflatex -interaction=nonstopmode -halt-on-error paper.tex
```

Then run:

```sh
python3 /Users/admin/.codex/skills/evidence-press-publication/scripts/pdf_tex_preflight.py paper.pdf
python3 verify_package.py --semantic-c16
```

The absolute preflight path is preparation-workflow infrastructure. It is not
required to check the mathematical certificates. The built PDF has ten pages,
extractable text, and zero raw-TeX findings in the recorded environment.

