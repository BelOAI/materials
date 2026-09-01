# Practices

Hands-on practice sessions live in `practices/[number]-[name]/` with the same folder layout as lectures:

```
practices/02-contest-warmup/
  main.tex       # driver: use [practice] option for teal-green theme
  meta.yaml      # site index metadata
  slides/        # numbered slide fragments
  assets/        # optional images
  materials/     # notebooks, PDFs, archives
```

See [`../lectures/README.md`](../lectures/README.md) for the full `meta.yaml` schema, `references`, and `materials` blocks.

## Naming

Use a numeric prefix for human-readable labels on the site (e.g. «Практика 2»), e.g. `01-warmup`, `02-contest`. The **site sort order** is determined by `date` and `slot`/`time` in `meta.yaml`, not the folder prefix.

Independent numbering from `lectures/` is fine — `lectures/03-foo` and `practices/03-foo` can coexist.

Folders starting with `_` (e.g. `_template`) are excluded from CI builds.

## Quick start

```bash
cp -R practices/_template practices/02-my-practice
# edit meta.yaml (set build: true), main.tex, slides/*
# add materials/ and references (contest links) as needed
make session DIR=practices/02-my-practice
make site   # regenerate index
```

## Theme

Practices use the teal-green palette:

```latex
\usepackage[practice,russian]{academicbeamer}  % or [practice,english]
\setshorttitle{BelOAI \textbar\ Практика 2}
```

See [`../latex/README.md`](../latex/README.md) for all package options.

## License

Practice slides, metadata, and assets are [CC BY 4.0](../LICENSE-CC-BY-4.0). Copyright: Pavel Kasila and BelOAI Material Authors. See [`../LICENSE`](../LICENSE) and [`../LICENSING.md`](../LICENSING.md).
