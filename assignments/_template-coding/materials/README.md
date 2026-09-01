# Materials

Place supplementary files for this assignment here and list them in `meta.yaml` under `materials:`.

| File type | Published as |
| --------- | ------------ |
| `.ipynb` | Browsable HTML + downloadable notebook |
| `.pdf`, `.zip`, `.csv`, `.py`, … | Direct download |

Example `meta.yaml` entry:

```yaml
materials:
  - path: materials/starter.py
    label: Шаблон решения
```

Build copies files to `_site/materials/<assignment-slug>/` during `make site`.
