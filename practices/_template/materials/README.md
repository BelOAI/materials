# Materials

Place supplementary files for this lecture here and list them in `meta.yaml` under `materials:`.

| File type | Published as |
| --------- | ------------ |
| `.ipynb` | Browsable HTML + downloadable notebook |
| `.pdf`, `.zip`, `.csv`, `.py`, … | Direct download |

Example `meta.yaml` entry:

```yaml
materials:
  - path: materials/notebook.ipynb
    label: Jupyter Notebook
```

Build copies files to `_site/materials/<lecture-slug>/` during `make site`.
