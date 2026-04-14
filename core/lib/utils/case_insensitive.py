class CaseInsensitiveDict(dict):
    def __init__(self, *args, **kwargs):
        self._lower_keys = {}
        super().__init__(*args, **kwargs)
        for k in super().keys():
            self._lower_keys[k.lower()] = k

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._lower_keys[key.lower()] = key

    def __getitem__(self, key):
        lower_key = key.lower()
        actual_key = self._lower_keys.get(lower_key, key)
        return super().__getitem__(actual_key)

    def __contains__(self, key):
        return key.lower() in self._lower_keys

    def get(self, key, default=None):
        lower_key = key.lower()
        actual_key = self._lower_keys.get(lower_key)
        if actual_key is None:
            return default
        return super().__getitem__(actual_key)

    def __delitem__(self, key):
        lower_key = key.lower()
        actual_key = self._lower_keys.pop(lower_key, key)
        super().__delitem__(actual_key)

    def pop(self, key, *args):
        lower_key = key.lower()
        actual_key = self._lower_keys.pop(lower_key, key)
        return super().pop(actual_key, *args)

    def setdefault(self, key, default=None):
        lower_key = key.lower()
        if lower_key in self._lower_keys:
            return self[lower_key]
        self[key] = default
        return default

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        for key in args[0] if args else kwargs:
            self._lower_keys[key.lower()] = key

    def keys(self):
        return list(self._lower_keys.values())

    def items(self):
        return [(k, self[k]) for k in self._lower_keys.values()]

    def values(self):
        return [self[k] for k in self._lower_keys.values()]
