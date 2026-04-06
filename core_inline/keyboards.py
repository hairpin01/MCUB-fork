class InlineKeyboards:
    def __init__(self, kernel):
        self.kernel = kernel
        self.lang = getattr(kernel, "lang", {}) or {}
