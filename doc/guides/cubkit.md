# CubKit

← [Index](../../API_DOC.md) · [Getting started](../getting-started/index.md)

**CubKit** is a small builder for MCUB modules. It lets you write a module as a
normal multi-file project and pack it into one `.py` file that MCUB can load from
`modules_loaded/`.

Typical layout:

```text
my_module/
  cubkit.toml
  main.py
  my_module_lib/
    utils.py
```

Build:

```bash
cubkit check .
cubkit build .
```

Use CubKit when a module needs helper files, private imports, generated metadata,
or a single-file release artifact.

Full CubKit documentation:
[github.com/hairpin01/CubKit/blob/main/doc/index.md](https://github.com/hairpin01/CubKit/blob/main/doc/index.md)
