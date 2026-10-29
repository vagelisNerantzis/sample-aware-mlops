# Architecture figure

`architecture.svg` shows the sample-aware control plane and the conceptual
roles of the four companion repositories. It uses plain SVG, system fonts,
and no external images, rendering services, or graph dependencies.

Regenerate from the repository root:

```console
python assets/generate_architecture.py
```

Verify without writing:

```console
python assets/generate_architecture.py --check
```

`render_svg()` returns a deterministic string. The generator writes UTF-8
bytes with LF line endings, without timestamps, random IDs, or environment
values. CI regenerates the figure and requires an empty Git diff.
