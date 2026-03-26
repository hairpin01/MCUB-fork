# author: @Hairpin00
# version: 2.1.0-beta
# description: Advanced API protection with deep request analytics + MCUB native protection

import asyncio
import time
import json
import math
import datetime
from collections import deque, defaultdict
from telethon import Button
from telethon.tl import TLRequest

DEFAULT_CONFIG = {
    "time_sample": 30,
    "threshold": 200,
    "local_floodwait": 30,
    "ignore_methods": ["GetMessagesRequest"],
    "enable_protection": True,
    # --- Telethon-MCUB native protection ---
    # mode: 'off' | 'safe' | 'strict' | 'custom'
    "mcub_mode": "safe",
    "mcub_dry_run": False,  # наблюдать нарушения без блокировки
    "mcub_allowlist": [],  # методы-исключения в custom-режиме
    # анализ
    "enable_analytics": True,
    "zscore_threshold": 3.0,
    "warn_percent": 90,
    "predict_window": 10,
    "baseline_window": 300,
    "profile_min_samples": 50,
    "predict_alert_cooldown": 10,
    "warn_alert_cooldown": 30,
}


class RequestAnalyzer:
    """
    Four-layer deep analysis of API request patterns:

    1. Multi-window counters   — simultaneous 1s / 5s / 15s / 60s windows
    2. Z-score anomaly score   — current rate vs. rolling baseline (mean ± σ)
    3. Predictive ETA          — linear rate extrapolation to threshold breach
    4. Method correlation graph — bigram transitions + cosine similarity to
                                  hourly behavioral profile
    """

    WINDOWS = [1, 5, 15, 60]

    def __init__(self, request_log: deque, ignore_set_fn, config: dict):
        self._log = request_log
        self._ignore_set = ignore_set_fn  # callable → set[str]
        self._cfg = config

        # Z-score baseline: per-second bucket → count
        self._sec_buckets: dict[int, int] = {}

        # Method transition graph: (prev, curr) → count
        self._transitions: defaultdict = defaultdict(int)
        self._last_method: str | None = None

        # Hourly behavioral profile: hour → method → count
        self._hourly_profile: dict[int, defaultdict] = defaultdict(
            lambda: defaultdict(int)
        )
        self._hourly_total: dict[int, int] = defaultdict(int)

        # Anomaly event log
        self.anomaly_log: deque = deque(maxlen=200)

        # Exponential-backoff state
        self.trigger_count: int = 0
        self.last_trigger_at: float = 0.0

    def record(self, method: str, ts: float) -> None:
        sec = int(ts)
        self._sec_buckets[sec] = self._sec_buckets.get(sec, 0) + 1

        # Prune buckets older than baseline_window
        cutoff_sec = sec - self._cfg.get("baseline_window", 300)
        old = [k for k in self._sec_buckets if k < cutoff_sec]
        for k in old:
            del self._sec_buckets[k]

        # Transition graph
        if self._last_method is not None:
            self._transitions[(self._last_method, method)] += 1
        self._last_method = method

        # Hourly profile
        hour = datetime.datetime.fromtimestamp(ts).hour
        self._hourly_profile[hour][method] += 1
        self._hourly_total[hour] += 1

    def window_counts(self, now: float) -> dict:
        """Returns {window_seconds: {'total': N, 'relevant': N}} for all WINDOWS."""
        ignore = self._ignore_set()
        result = {}
        for w in self.WINDOWS:
            cutoff = now - w
            total = 0
            relevant = 0
            for m, ts in self._log:
                if ts > cutoff:
                    total += 1
                    if m not in ignore:
                        relevant += 1
            result[w] = {"total": total, "relevant": relevant}
        return result

    def zscore(self, now: float) -> float:
        """
        Z-score of the current 5-second request rate versus the rolling baseline.
        Returns 0.0 if there is not enough baseline data yet.
        """
        measure_window = 5
        baseline_sec = self._cfg.get("baseline_window", 300)

        # Current rate (req/s) over last measure_window seconds
        cutoff_now = now - measure_window
        current_count = sum(1 for _, ts in self._log if ts > cutoff_now)
        current_rate = current_count / measure_window

        # Baseline: per-second counts excluding the measurement window
        now_sec = int(now)
        baseline_floor = now_sec - baseline_sec
        baseline_vals = [
            v
            for k, v in self._sec_buckets.items()
            if baseline_floor <= k < now_sec - measure_window
        ]

        if len(baseline_vals) < 10:
            return 0.0

        mean = sum(baseline_vals) / len(baseline_vals)
        variance = sum((x - mean) ** 2 for x in baseline_vals) / len(baseline_vals)
        std = math.sqrt(variance)

        if std < 1e-6:
            return 0.0

        return (current_rate - mean) / std

    def acceleration(self, now: float) -> float:
        """
        Rate-of-change of request rate (req/s²).
        Positive → accelerating, negative → slowing down.
        """
        ignore = self._ignore_set()
        recent = (
            sum(1 for m, ts in self._log if now - 5 < ts <= now and m not in ignore) / 5
        )
        prior = (
            sum(
                1 for m, ts in self._log if now - 10 < ts <= now - 5 and m not in ignore
            )
            / 5
        )
        return recent - prior

    def predict_eta(self, now: float, threshold: int) -> float | None:
        """
        Estimate seconds until the relevant-request count hits `threshold`.
        Uses current rate + acceleration for a 2nd-order estimate.
        Returns None if the current trend is flat/decreasing (no breach predicted).
        Returns 0.0 if already at/above threshold.
        """
        ignore = self._ignore_set()
        pw = self._cfg.get("predict_window", 10)
        tw = self._cfg.get("time_sample", 15)

        # Current accumulation in the monitoring window
        current = sum(1 for m, ts in self._log if ts > now - tw and m not in ignore)
        if current >= threshold:
            return 0.0

        # Rate over predict_window
        rate = sum(1 for m, ts in self._log if ts > now - pw and m not in ignore) / pw
        if rate <= 0:
            return None

        accel = self.acceleration(now)
        remaining = threshold - current

        if abs(accel) < 1e-6:
            # constant rate
            return remaining / rate

        # Solve: remaining = rate*t + 0.5*accel*t²  →  quadratic
        # 0.5*a*t² + rate*t - remaining = 0
        a_coef = 0.5 * accel
        b_coef = rate
        c_coef = -remaining

        discriminant = b_coef**2 - 4 * a_coef * c_coef
        if discriminant < 0 or a_coef == 0:
            return remaining / rate if rate > 0 else None

        t1 = (-b_coef + math.sqrt(discriminant)) / (2 * a_coef)
        t2 = (-b_coef - math.sqrt(discriminant)) / (2 * a_coef)

        # Pick smallest positive root
        candidates = [t for t in (t1, t2) if t > 0]
        return min(candidates) if candidates else None

    def top_transitions(self, limit: int = 5) -> list:
        """Most frequent (prev, curr) method pairs."""
        return sorted(self._transitions.items(), key=lambda x: x[1], reverse=True)[
            :limit
        ]

    def anomalous_transitions(self, z_thresh: float = 2.5) -> list:
        """
        Transition pairs whose frequency significantly exceeds the mean.
        Returns list of ((prev, curr), count, z_score).
        """
        if len(self._transitions) < 3:
            return []

        vals = list(self._transitions.values())
        mean = sum(vals) / len(vals)
        std = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))

        if std < 1e-6:
            return []

        out = []
        for pair, count in self._transitions.items():
            z = (count - mean) / std
            if z > z_thresh:
                out.append((pair, count, round(z, 2)))

        return sorted(out, key=lambda x: x[2], reverse=True)[:5]

    def cosine_similarity(self, now: float) -> float | None:
        """
        Cosine similarity between the current 60-second method distribution
        and the stored hourly behavioral profile.
        Returns None if there are not enough profile samples yet.
        """
        hour = datetime.datetime.fromtimestamp(now).hour
        profile = self._hourly_profile.get(hour)
        total_p = self._hourly_total.get(hour, 0)
        min_s = self._cfg.get("profile_min_samples", 50)

        if not profile or total_p < min_s:
            return None

        current: defaultdict = defaultdict(int)
        for m, ts in self._log:
            if ts > now - 60:
                current[m] += 1

        if not current:
            return None

        all_methods = set(profile.keys()) | set(current.keys())
        total_c = sum(current.values())

        vec_p = [profile.get(m, 0) / total_p for m in all_methods]
        vec_c = [current.get(m, 0) / total_c for m in all_methods]

        dot = sum(a * b for a, b in zip(vec_p, vec_c))
        mag_p = math.sqrt(sum(a * a for a in vec_p))
        mag_c = math.sqrt(sum(b * b for b in vec_c))

        if mag_p < 1e-9 or mag_c < 1e-9:
            return None

        return dot / (mag_p * mag_c)

    def backoff_seconds(self) -> float:
        """Returns the next block duration with exponential growth (capped at 10 min)."""
        base = self._cfg.get("local_floodwait", 30)
        return min(base * (2 ** min(self.trigger_count, 5)), 600)

    def on_trigger(self, now: float) -> None:
        self.trigger_count += 1
        self.last_trigger_at = now

    def maybe_reset_backoff(self, now: float) -> None:
        """Auto-reset trigger counter after a long quiet period."""
        quiet_threshold = self._cfg.get("local_floodwait", 30) * 4
        if self.trigger_count > 0 and now - self.last_trigger_at > quiet_threshold:
            self.trigger_count = 0

    def reset(self) -> None:
        self._sec_buckets.clear()
        self._transitions.clear()
        self._last_method = None
        self._hourly_profile.clear()
        self._hourly_total.clear()
        self.anomaly_log.clear()
        self.trigger_count = 0
        self.last_trigger_at = 0.0

    def full_report(self, now: float, threshold: int, lang: dict) -> str:
        ignore = self._ignore_set()
        windows = self.window_counts(now)
        z = self.zscore(now)
        eta = self.predict_eta(now, threshold)
        accel = self.acceleration(now)
        cosine = self.cosine_similarity(now)
        top_tr = self.top_transitions(5)
        anom_tr = self.anomalous_transitions()

        win_lines = []
        for w in self.WINDOWS:
            d = windows[w]
            win_lines.append(
                f"  `{w:>2}s` — all: **{d['total']}**  /  relevant: **{d['relevant']}**"
            )

        z_str = f"**{z:+.2f}σ**"
        z_flag = " ⚠️" if abs(z) >= self._cfg.get("zscore_threshold", 3.0) else ""

        # ETA
        if eta is None:
            eta_str = lang["analyze_eta_safe"]
        elif eta == 0.0:
            eta_str = lang["analyze_eta_now"]
        else:
            eta_str = lang["analyze_eta_in"].format(seconds=round(eta, 1))

        accel_str = f"{accel:+.2f} req/s²"
        accel_flag = " 🚀" if accel > 2 else (" 🐢" if accel < -2 else "")

        if cosine is None:
            cosine_str = lang["analyze_profile_insufficient"]
        else:
            pct = round(cosine * 100, 1)
            flag = " ⚠️" if pct < 60 else ""
            cosine_str = f"**{pct}%**{flag}"

        if top_tr:
            tr_lines = "\n".join(f"  `{p}→{c}`: {n}x" for (p, c), n in top_tr)
        else:
            tr_lines = "  —"

        if anom_tr:
            anom_lines = "\n".join(
                f"  `{p}→{c}`: {n}x  (z={z})" for (p, c), n, z in anom_tr
            )
        else:
            anom_lines = "  —"

        backoff_str = f"{self.backoff_seconds():.0f}s (trigger #{self.trigger_count})"

        return lang["api_analyze_report"].format(
            windows="\n".join(win_lines),
            zscore=z_str + z_flag,
            threshold=threshold,
            eta=eta_str,
            accel=accel_str + accel_flag,
            cosine=cosine_str,
            transitions=tr_lines,
            anomalous=anom_lines,
            backoff=backoff_str,
        )


def register(kernel):
    client = kernel.client
    language = kernel.config.get("language", "en")

    strings = {
        "ru": {
            "api_protection_enabled": "✅ API защита включена",
            "api_protection_disabled": "❌ API защита выключена",
            "api_protection_usage": "Использование: .api_protection [on/off] [параметр значение]",
            "are_you_sure": "Вы уверены?",
            "yes": "Да",
            "no": "Нет",
            "api_protection_on": "защита <b>включена</b>",
            "api_protection_off": "защита <b>выключена</b>",
            "too_many_requests": "<i>Слишком много запросов</i>",
            "bot_stopped": '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji> Бот остановлен на <b>{seconds}</b> секунд',
            "bot_unlocked": '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji> Бот разблокирован после <b>{seconds}</b> секунд ожидания',
            "request_limit_exceeded": "<b>Превышен лимит запросов</b> (<u>{limit_type}</u>)",
            "insufficient_permissions": '<tg-emoji emoji-id="5388785832956016892">❌</tg-emoji> <b>Недостаточно прав</b>',
            "limits_reset": '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji> <b>Лимиты сброшены</b>',
            "processing": "⏳ Обработка...",
            "error_processing": '<tg-emoji emoji-id="5388785832956016892">❌</tg-emoji> <b>Ошибка обработки</b>',
            "api_stats": '<tg-emoji emoji-id="5431736674147114227">📋</tg-emoji> <b>Статистика API</b>\n'
            "<blockquote>⏱ За последние <b>{interval}</b>с</blockquote>\n"
            "• <u>Всего запросов</u>: <b>{total_all}</b>\n"
            "• <u>Учитываемых</u>: <b>{total_relevant}</b>\n"
            '<tg-emoji emoji-id="5431736674147114227">📋</tg-emoji> <b>Топ методов (все):</b>\n{methods}',
            "api_stats_empty": '<tg-emoji emoji-id="5431736674147114227">📋</tg-emoji> <i>Нет запросов за последние {interval}с</i>',
            "api_reset_done": '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji> <b>Статистика, аналитика и блокировка сброшены</b>',
            "api_suspend": '<tg-emoji emoji-id="5372892693024218813">🥶</tg-emoji> <b>Защита приостановлена</b> на <code>{seconds}</code>с',
            "api_param_set": '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji> Параметр <code>{param}</code> установлен в <code>{value}</code>',
            "api_param_error": '<tg-emoji emoji-id="5388785832956016892">❌</tg-emoji> <b>Неверный параметр или значение</b>',
            "api_overload_notify": '<tg-emoji emoji-id="5904692292324692386">⚠️</tg-emoji> <b>Превышение лимита API!</b>\n'
            "<blockquote>⏱ Учитываемых запросов за <b>{interval}</b>с: <b>{total}</b> (порог <u>{threshold}</u>)</blockquote>\n"
            "• <b>Триггер</b>: <code>{trigger}</code>\n"
            "• <b>Блокировка</b>: <code>{block_seconds}</code>с (попытка #{trigger_count})\n"
            '<tg-emoji emoji-id="5431736674147114227">📋</tg-emoji> <b>Топ методов:</b>\n{methods}',
            "api_warn_threshold": '<tg-emoji emoji-id="5406792732452613826">🔶</tg-emoji> <b>Предупреждение API</b>: <i>{percent}%</i> от порога (<code>{current}/{threshold}</code> за <b>{interval}</b>с)',
            "api_predict_block": '<tg-emoji emoji-id="5445259009311391329">🔮</tg-emoji> <b>Предиктивное предупреждение</b>: превышение порога через <code>~{eta}</code>с\n'
            "<blockquote>⚡ Ускорение: <u>{accel}</u> req/s²</blockquote>",
            "api_ignore_usage": '<tg-emoji emoji-id="5332654441508119011">⚙️</tg-emoji> <b>Использование:</b> <code>.api_ignore [list|add|remove|clear] [method]</code>',
            "api_ignore_list": '<tg-emoji emoji-id="5431736674147114227">📋</tg-emoji> <b>Игнорируемые методы:</b>\n<code>{methods}</code>',
            "api_ignore_list_empty": '<tg-emoji emoji-id="5431736674147114227">📋</tg-emoji> <i>Список игнорируемых методов пуст</i>',
            "api_ignore_added": '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji> Метод <code>{method}</code> добавлен в игнорируемые',
            "api_ignore_removed": '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji> Метод <code>{method}</code> удалён из игнорируемых',
            "api_ignore_cleared": '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji> <b>Список игнорируемых методов очищен</b>',
            "api_ignore_not_found": '<tg-emoji emoji-id="5388785832956016892">❌</tg-emoji> Метод <code>{method}</code> не найден в списке',
            "api_analyze_report": (
                '<tg-emoji emoji-id="4904936030232117798">🔬</tg-emoji> <b>Глубокий анализ API</b>\n\n'
                '<tg-emoji emoji-id="5431736674147114227">📋</tg-emoji> <b>Многоуровневые окна</b>\n<code>{windows}</code>\n\n'
                '<tg-emoji emoji-id="5373001317042101552">📈</tg-emoji> <b>Z-score аномалии</b>: <code>{zscore}</code>  <i>(порог ±{threshold}σ)</i>\n'
                '<tg-emoji emoji-id="5445259009311391329">🔮</tg-emoji> <b>Прогноз до превышения</b>: <code>{eta}</code>\n'
                '<tg-emoji emoji-id="5383140876316669109">⚡</tg-emoji> <b>Ускорение</b>: <code>{accel}</code>\n\n'
                '<tg-emoji emoji-id="5368513458469878442">🧬</tg-emoji> <b>Сходство с профилем</b>: <code>{cosine}</code>\n\n'
                '<tg-emoji emoji-id="5264727218734524899">🔀</tg-emoji> <b>Топ переходов методов</b>:\n<code>{transitions}</code>\n\n'
                '<tg-emoji emoji-id="5370872220149099318">🚨</tg-emoji> <b>Аномальные переходы</b>:\n<code>{anomalous}</code>\n\n'
                '<tg-emoji emoji-id="5422742359930356292">⏱</tg-emoji> <b>Следующая блокировка (backoff)</b>: <code>{backoff}</code>'
            ),
            "analyze_eta_safe": '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji> <i>Не ожидается</i>',
            "analyze_eta_now": '<tg-emoji emoji-id="5388785832956016892">❌</tg-emoji> <b>Уже превышен</b>',
            "analyze_eta_in": "<code>~{seconds}</code>с",
            "analyze_profile_insufficient": "<i>недостаточно данных</i>",
            "mcub_not_supported": '<tg-emoji emoji-id="5904692292324692386">⚠️</tg-emoji> <b>Telethon-MCUB не обнаружен</b> — штатная защита недоступна',
            "mcub_mode_set": '<tg-emoji emoji-id="5253671358734281000">🛡</tg-emoji> <b>Режим защиты MCUB:</b> <code>{mode}</code><i>{dry}</i>',
            "mcub_mode_dry": " <i>(dry-run: нарушения логируются, не блокируются)</i>",
            "mcub_mode_usage": '<tg-emoji emoji-id="5332654441508119011">⚙️</tg-emoji> <b>Использование:</b> <code>.api_mode [off|safe|strict|custom] [dry]</code>',
            "mcub_violation": '<tg-emoji emoji-id="5767151002666929821">🚫</tg-emoji> <b>MCUB заблокировал запрос</b>\n'
            "<blockquote>• <b>Метод:</b> <code>{method}</code>\n"
            "• <b>Режим:</b> <code>{mode}</code>\n"
            "• <b>Причина:</b> <i>{reason}</i></blockquote>",
            "mcub_status": '<tg-emoji emoji-id="5253671358734281000">🛡</tg-emoji> <b>MCUB защита</b>\n'
            "<blockquote>• <b>Режим:</b> <code>{mode}</code>\n"
            "• <b>Dry-run:</b> <i>{dry}</i>\n"
            "• <b>Allowlist:</b> <code>{allowlist}</code></blockquote>",
            "mcub_choose_mode": '<tg-emoji emoji-id="5253671358734281000">🛡</tg-emoji> <b>Выбери режим защиты MCUB:</b>',
            "mcub_mode_default": "👾 По умолчанию ({mode})",
        },
        "en": {
            "api_protection_enabled": '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji> <b>API protection enabled</b>',
            "api_protection_disabled": '<tg-emoji emoji-id="5388785832956016892">❌</tg-emoji> <b>API protection disabled</b>',
            "api_protection_usage": '<tg-emoji emoji-id="5332654441508119011">⚙️</tg-emoji> <b>Usage:</b> <code>.api_protection [on/off] [parameter value]</code>',
            "are_you_sure": "<i>Are you sure?</i>",
            "yes": "Yes",
            "no": "No",
            "api_protection_on": "<b>api protection enabled</b>",
            "api_protection_off": "<b>api protection disabled</b>",
            "too_many_requests": "<i>Too many requests</i>",
            "bot_stopped": '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji> Bot stopped for <b>{seconds}</b> seconds',
            "bot_unlocked": '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji> Bot unlocked after <b>{seconds}</b> seconds of waiting',
            "request_limit_exceeded": "<b>Request limit exceeded</b> (<u>{limit_type}</u>)",
            "insufficient_permissions": '<tg-emoji emoji-id="5388785832956016892">❌</tg-emoji> <b>Insufficient permissions</b>',
            "limits_reset": '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji> <b>Limits reset</b>',
            "processing": "⏳ Processing...",
            "error_processing": '<tg-emoji emoji-id="5388785832956016892">❌</tg-emoji> <b>Error processing</b>',
            "api_stats": '<tg-emoji emoji-id="5431736674147114227">📋</tg-emoji> <b>API Statistics</b>\n'
            "<blockquote>⏱ Last <b>{interval}</b>s</blockquote>\n"
            "• <u>Total requests</u>: <b>{total_all}</b>\n"
            "• <u>Relevant</u>: <b>{total_relevant}</b>\n"
            '<tg-emoji emoji-id="5431736674147114227">📋</tg-emoji> <b>Top methods (all):</b>\n{methods}',
            "api_stats_empty": '<tg-emoji emoji-id="5431736674147114227">📋</tg-emoji> <i>No requests in last {interval}s</i>',
            "api_reset_done": '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji> <b>Stats, analytics and block reset</b>',
            "api_suspend": '<tg-emoji emoji-id="5372892693024218813">🥶</tg-emoji> <b>Protection suspended</b> for <code>{seconds}</code>s',
            "api_param_set": '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji> Parameter <code>{param}</code> set to <code>{value}</code>',
            "api_param_error": '<tg-emoji emoji-id="5388785832956016892">❌</tg-emoji> <b>Invalid parameter or value</b>',
            "api_overload_notify": '<tg-emoji emoji-id="5904692292324692386">⚠️</tg-emoji> <b>API overload detected!</b>\n'
            "<blockquote>⏱ Relevant requests in last <b>{interval}</b>s: <b>{total}</b> (threshold <u>{threshold}</u>)</blockquote>\n"
            "• <b>Trigger method:</b> <code>{trigger}</code>\n"
            "• <b>Blocking for:</b> <code>{block_seconds}</code>s (attempt #{trigger_count})\n"
            '<tg-emoji emoji-id="5431736674147114227">📋</tg-emoji> <b>Top methods:</b>\n{methods}',
            "api_warn_threshold": '<tg-emoji emoji-id="5406792732452613826">🔶</tg-emoji> <b>API warning</b>: <i>{percent}%</i> of threshold (<code>{current}/{threshold}</code> in <b>{interval}</b>s)',
            "api_predict_block": '<tg-emoji emoji-id="5445259009311391329">🔮</tg-emoji> <b>Predictive alert</b>: threshold breach in <code>~{eta}</code>s\n'
            "<blockquote>⚡ Acceleration: <u>{accel}</u> req/s²</blockquote>",
            "api_ignore_usage": '<tg-emoji emoji-id="5332654441508119011">⚙️</tg-emoji> <b>Usage:</b> <code>.api_ignore [list|add|remove|clear] [method]</code>',
            "api_ignore_list": '<tg-emoji emoji-id="5431736674147114227">📋</tg-emoji> <b>Ignored methods:</b>\n<code>{methods}</code>',
            "api_ignore_list_empty": '<tg-emoji emoji-id="5431736674147114227">📋</tg-emoji> <i>Ignored methods list is empty</i>',
            "api_ignore_added": '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji> Method <code>{method}</code> added to ignore list',
            "api_ignore_removed": '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji> Method <code>{method}</code> removed from ignore list',
            "api_ignore_cleared": '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji> <b>Ignored methods list cleared</b>',
            "api_ignore_not_found": '<tg-emoji emoji-id="5388785832956016892">❌</tg-emoji> Method <code>{method}</code> not found in ignore list',
            "api_analyze_report": (
                '<tg-emoji emoji-id="4904936030232117798">🔬</tg-emoji> <b>Deep API Analysis</b>\n\n'
                '<tg-emoji emoji-id="5431736674147114227">📋</tg-emoji> <b>Multi-window counters</b>\n<code>{windows}</code>\n\n'
                '<tg-emoji emoji-id="5373001317042101552">📈</tg-emoji> <b>Anomaly Z-score</b>: <code>{zscore}</code>  <i>(threshold ±{threshold}σ)</i>\n'
                '<tg-emoji emoji-id="5445259009311391329">🔮</tg-emoji> <b>Predicted breach ETA</b>: <code>{eta}</code>\n'
                '<tg-emoji emoji-id="5383140876316669109">⚡</tg-emoji> <b>Rate acceleration</b>: <code>{accel}</code>\n\n'
                '<tg-emoji emoji-id="5368513458469878442">🧬</tg-emoji> <b>Profile similarity</b>: <code>{cosine}</code>\n\n'
                '<tg-emoji emoji-id="5264727218734524899">🔀</tg-emoji> <b>Top method transitions</b>:\n<code>{transitions}</code>\n\n'
                '<tg-emoji emoji-id="5370872220149099318">🚨</tg-emoji> <b>Anomalous transitions</b>:\n<code>{anomalous}</code>\n\n'
                "⏱<b>Next block (backoff)</b>: <code>{backoff}</code>"
            ),
            "analyze_eta_safe": '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji> <i>Not expected</i>',
            "analyze_eta_now": '<tg-emoji emoji-id="5388785832956016892">❌</tg-emoji> <b>Already exceeded</b>',
            "analyze_eta_in": "<code>~{seconds}</code>s",
            "analyze_profile_insufficient": "<i>insufficient data</i>",
            "mcub_not_supported": '<tg-emoji emoji-id="5904692292324692386">⚠️</tg-emoji> <b>Telethon-MCUB not detected</b> — native protection unavailable',
            "mcub_mode_set": '<tg-emoji emoji-id="5253671358734281000">🛡</tg-emoji> <b>MCUB protection mode:</b> <code>{mode}</code><i>{dry}</i>',
            "mcub_mode_dry": " <i>(dry-run: violations logged, not blocked)</i>",
            "mcub_mode_usage": '<tg-emoji emoji-id="5332654441508119011">⚙️</tg-emoji> <b>Usage:</b> <code>.api_mode [off|safe|strict|custom] [dry]</code>',
            "mcub_violation": '<tg-emoji emoji-id="5767151002666929821">🚫</tg-emoji> <b>MCUB blocked a request</b>\n'
            "<blockquote>• <b>Method:</b> <code>{method}</code>\n"
            "• <b>Mode:</b> <code>{mode}</code>\n"
            "• <b>Reason:</b> <i>{reason}</i></blockquote>",
            "mcub_status": '<tg-emoji emoji-id="5253671358734281000">🛡</tg-emoji> <b>MCUB protection</b>\n'
            "<blockquote>• <b>Mode:</b> <code>{mode}</code>\n"
            "• <b>Dry-run:</b> <i>{dry}</i>\n"
            "• <b>Allowlist:</b> <code>{allowlist}</code></blockquote>",
            "mcub_choose_mode": '<tg-emoji emoji-id="5253671358734281000">🛡</tg-emoji> <b>Choose MCUB protection mode:</b>',
            "mcub_mode_default": "👾 Default ({mode})",
        },
    }

    lang = strings.get(language, strings["en"])

    raw_config = kernel.config.get("api_protection", DEFAULT_CONFIG.copy())
    if isinstance(raw_config, bool):
        api_config = DEFAULT_CONFIG.copy()
        api_config["enable_protection"] = raw_config
        kernel.logger.info(
            "Converted old api_protection config (bool) to new dict format"
        )
    else:
        api_config = raw_config
        for k, v in DEFAULT_CONFIG.items():
            if k not in api_config:
                api_config[k] = v

    kernel.config["api_protection"] = api_config

    def persist_api_config():
        kernel.config["api_protection"] = api_config
        kernel.save_config()

    protection_enabled = api_config["enable_protection"]
    blocked_until = 0.0
    original_call = None
    request_log = deque(maxlen=10000)
    last_predict_alert = 0.0
    last_warn_alert = 0.0
    predict_cooldown = api_config.get("predict_alert_cooldown", 10)
    warn_cooldown = api_config.get("warn_alert_cooldown", 30)

    analyzer = RequestAnalyzer(
        request_log=request_log,
        ignore_set_fn=lambda: set(api_config["ignore_methods"]),
        config=api_config,
    )

    _mcub_available = (
        hasattr(client, "set_protection_mode")
        and hasattr(client, "on_blocked_request")
        and hasattr(client, "set_protection_policy")
    )

    def _apply_mcub_mode(mode: str) -> bool:
        """
        Apply a protection mode to the MCUB client.
        Returns True on success, False if MCUB is not available.
        """
        if not _mcub_available:
            return False

        try:
            if mode == "custom":
                # Build a ProtectionPolicy from config allowlist + dry_run flag
                from telethon.client.protection import ProtectionPolicy

                allowlist = set(api_config.get("mcub_allowlist", []))
                dry_run = api_config.get("mcub_dry_run", False)
                policy = ProtectionPolicy(allowlist=allowlist, dry_run=dry_run)
                client.set_protection_policy(policy)
            else:
                client.set_protection_mode(mode)
            return True
        except Exception as e:
            kernel.logger.error(f"Failed to apply MCUB mode '{mode}': {e}")
            return False

    async def _mcub_violation_handler(violation) -> None:
        """
        Called by MCUB on every blocked (or dry-run observed) request.
        Logs to kernel.log_chat_id and feeds the analyzer.
        """
        try:
            method = getattr(violation, "method", None) or type(violation).__name__
            reason = getattr(violation, "reason", str(violation))
            mode = api_config.get("mcub_mode", "safe")

            kernel.logger.warning(f"MCUB violation [{mode}]: {method} — {reason}")

            # Feed into analytics so transitions / Z-score include blocked attempts
            now = time.time()
            request_log.append((method, now))
            if api_config.get("enable_analytics", True):
                analyzer.record(method, now)

            if not kernel.log_chat_id:
                return

            text = lang["mcub_violation"].format(
                method=method,
                mode=mode,
                reason=reason,
            )
            try:
                await kernel.client.send_message(
                    kernel.log_chat_id, text, parse_mode="html"
                )
            except Exception:
                try:
                    await kernel.client.send_message("me", text, parse_mode="html")
                except Exception:
                    pass
        except Exception as e:
            kernel.logger.error(f"MCUB violation handler error: {e}")

    async def api_call_interceptor(
        sender,
        request: TLRequest,
        ordered: bool = False,
        flood_sleep_threshold: int = None,
    ):
        nonlocal blocked_until, protection_enabled

        now = time.time()
        method = request.__class__.__name__

        if not protection_enabled:
            return await original_call(sender, request, ordered, flood_sleep_threshold)

        # Wait out any active block
        if now < blocked_until:
            await asyncio.sleep(blocked_until - now)
            now = time.time()

        # Record into both log and analyzer
        request_log.append((method, now))
        if api_config.get("enable_analytics", True):
            analyzer.record(method, now)
            analyzer.maybe_reset_backoff(now)

        interval = api_config["time_sample"]
        ignore_set = set(api_config["ignore_methods"])
        threshold = api_config["threshold"]
        cutoff = now - interval
        total_relevant = sum(
            1 for m, ts in request_log if ts > cutoff and m not in ignore_set
        )

        if total_relevant > threshold and now >= blocked_until:
            analyzer.on_trigger(now)
            block_dur = analyzer.backoff_seconds()
            blocked_until = now + block_dur
            kernel.logger.warning(
                f"API protection triggered (attempt #{analyzer.trigger_count}): "
                f"{total_relevant} relevant requests in {interval}s — "
                f"blocking for {block_dur:.0f}s"
            )
            asyncio.create_task(
                notify_overload(
                    kernel,
                    lang,
                    method,
                    total_relevant,
                    interval,
                    threshold,
                    block_dur,
                    analyzer.trigger_count,
                )
            )
            return await original_call(sender, request, ordered, flood_sleep_threshold)

        if not api_config.get("enable_analytics", True):
            return await original_call(sender, request, ordered, flood_sleep_threshold)

        warn_pct = api_config.get("warn_percent", 90)
        eta = analyzer.predict_eta(now, threshold)
        accel = analyzer.acceleration(now)
        predict_cooldown = api_config.get("predict_alert_cooldown", 10)
        warn_cooldown = api_config.get("warn_alert_cooldown", 30)

        nonlocal last_predict_alert, last_warn_alert

        if total_relevant >= threshold * warn_pct / 100 and total_relevant < threshold:
            if now - last_warn_alert >= warn_cooldown:
                last_warn_alert = now
                pct = round(total_relevant / threshold * 100)
                asyncio.create_task(
                    send_warn(
                        kernel,
                        lang["api_warn_threshold"].format(
                            percent=pct,
                            current=total_relevant,
                            threshold=threshold,
                            interval=interval,
                        ),
                    )
                )

        elif eta is not None and 0 < eta < 5 and accel > 0:
            if now - last_predict_alert >= predict_cooldown:
                last_predict_alert = now
                asyncio.create_task(
                    send_warn(
                        kernel,
                        lang["api_predict_block"].format(
                            eta=round(eta, 1),
                            accel=round(accel, 2),
                        ),
                    )
                )

        return await original_call(sender, request, ordered, flood_sleep_threshold)

    @kernel.register.on_load()
    async def install_interceptor(kernel):
        nonlocal original_call
        if hasattr(client, "_original_call"):
            kernel.logger.debug("API interceptor already installed")
            return
        original_call = client._call
        client._call = api_call_interceptor
        client._original_call = original_call

        # Apply MCUB protection mode on startup
        if _mcub_available:
            mode = api_config.get("mcub_mode", "safe")
            if _apply_mcub_mode(mode):
                client.on_blocked_request(_mcub_violation_handler)
                kernel.logger.info(f"MCUB protection mode set to '{mode}'")
            else:
                kernel.logger.warning("MCUB mode apply failed on load")
        else:
            kernel.logger.debug(
                "Telethon-MCUB not detected, skipping native protection setup"
            )

    @kernel.register.uninstall()
    async def uninstall_interceptor(kernel):
        nonlocal original_call
        if hasattr(client, "_original_call"):
            client._call = client._original_call
            delattr(client, "_original_call")
            kernel.logger.info("API call interceptor uninstalled")

        # Remove MCUB violation handler and reset to safe mode
        if _mcub_available:
            try:
                client.clear_blocked_request_handler()
                client.set_protection_mode("safe")
                kernel.logger.info("MCUB protection reset to 'safe' on uninstall")
            except Exception as e:
                kernel.logger.warning(f"MCUB cleanup error: {e}")

    async def send_warn(kernel, text: str):
        if not kernel.log_chat_id:
            return
        try:
            await kernel.bot_client.send_message(
                kernel.log_chat_id, text, parse_mode="html"
            )
        except (TypeError, AttributeError, ValueError):
            await kernel.client.send_message(
                kernel.log_chat_id, text, parse_mode="html"
            )
        except Exception as e:
            kernel.logger.error(f"send warn error: {e}")

    async def notify_overload(
        kernel,
        lang,
        trigger_method,
        total_relevant,
        interval,
        threshold,
        block_seconds,
        trigger_count,
    ):
        if not kernel.log_chat_id:
            return

        now = time.time()
        cutoff = now - interval

        method_counts: defaultdict = defaultdict(int)
        for m, ts in request_log:
            if ts > cutoff:
                method_counts[m] += 1

        top_methods = sorted(method_counts.items(), key=lambda x: x[1], reverse=True)[
            :5
        ]
        methods_str = "\n".join(f"  `{m}`: {c}" for m, c in top_methods)

        text = lang["api_overload_notify"].format(
            interval=interval,
            total=total_relevant,
            threshold=threshold,
            trigger=trigger_method,
            block_seconds=int(block_seconds),
            trigger_count=trigger_count,
            methods=methods_str,
        )

        import io, csv

        filtered_log = [(ts, m) for m, ts in request_log if ts > cutoff]
        filtered_log.sort(key=lambda x: x[0])

        str_buf = io.StringIO()
        writer = csv.writer(str_buf)
        writer.writerow(["timestamp", "method"])
        for ts, m in filtered_log:
            writer.writerow([int(ts), m])

        file_name = f"api_requests_{int(now)}.csv"
        buf = io.BytesIO(str_buf.getvalue().encode("utf-8"))
        buf.name = file_name
        buf.seek(0)

        for sender in (getattr(kernel, "bot_client", None), kernel.client):
            if sender is None:
                continue
            try:
                await sender.send_file(
                    kernel.log_chat_id,
                    buf,
                    caption=text,
                    file_name=file_name,
                    force_document=True,
                    parse_mode="html",
                )
                return
            except Exception:
                buf.seek(0)

        try:
            await kernel.client.send_message("me", text)
        except Exception:
            pass

    @kernel.register.command("api_protection")
    async def api_protection_handler(event):
        nonlocal protection_enabled
        args = event.text.split()

        if len(args) == 1:
            buttons = [
                [
                    Button.inline(lang["yes"], b"api_protection_yes"),
                    Button.inline(lang["no"], b"api_protection_no"),
                ],
            ]
            await kernel.inline_form(
                event.chat_id, lang["are_you_sure"], buttons=buttons
            )
            await event.delete()
            return

        subcmd = args[1].lower()
        if subcmd in ("on", "enable", "true"):
            protection_enabled = api_config["enable_protection"] = True
            await event.edit(lang["api_protection_enabled"], parse_mode="html")
        elif subcmd in ("off", "disable", "false"):
            protection_enabled = api_config["enable_protection"] = False
            await event.edit(lang["api_protection_disabled"], parse_mode="html")
        elif len(args) >= 3:
            param = args[1]
            value = " ".join(args[2:])
            if param in api_config:
                try:
                    if isinstance(api_config[param], list):
                        new_val = json.loads(value)
                        if not isinstance(new_val, list):
                            raise ValueError
                        api_config[param] = new_val
                    elif isinstance(api_config[param], bool):
                        api_config[param] = value.lower() in ("true", "yes", "1")
                    elif isinstance(api_config[param], (int, float)):
                        api_config[param] = type(api_config[param])(value)
                    else:
                        api_config[param] = value
                    await event.edit(
                        lang["api_param_set"].format(
                            param=param, value=api_config[param]
                        )
                    )
                except Exception:
                    await event.edit(lang["api_param_error"], parse_mode="html")
                    return
            else:
                await event.edit(lang["api_param_error"], parse_mode="html")
                return
        else:
            await event.edit(lang["api_protection_usage"], parse_mode="html")
            return

        persist_api_config()

    @kernel.register.command("api_reset")
    async def api_reset_handler(event):
        nonlocal blocked_until
        request_log.clear()
        analyzer.reset()
        blocked_until = 0.0
        await event.edit(lang["api_reset_done"], parse_mode="html")

    @kernel.register.command("api_suspend")
    async def api_suspend_handler(event):
        nonlocal blocked_until
        args = event.text.split()
        if len(args) != 2 or not args[1].isdigit():
            await event.edit(lang["api_protection_usage"], parse_mode="html")
            return
        seconds = int(args[1])
        blocked_until = time.time() + seconds
        await event.edit(lang["api_suspend"].format(seconds=seconds), parse_mode="html")

    @kernel.register.command("api_ignore")
    async def api_ignore_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(lang["api_ignore_usage"], parse_mode="html")
            return

        subcmd = args[1].lower()

        if subcmd == "list":
            methods = api_config["ignore_methods"]
            if not methods:
                await event.edit(lang["api_ignore_list_empty"], parse_mode="html")
            else:
                methods_str = "\n".join(f"  • `{m}`" for m in methods)
                await event.edit(
                    lang["api_ignore_list"].format(methods=methods_str),
                    parse_mode="html",
                )

        elif subcmd == "add" and len(args) >= 3:
            method = args[2]
            if method not in api_config["ignore_methods"]:
                api_config["ignore_methods"].append(method)
                persist_api_config()
            await event.edit(
                lang["api_ignore_added"].format(method=method), parse_mode="html"
            )

        elif subcmd == "remove" and len(args) >= 3:
            method = args[2]
            if method in api_config["ignore_methods"]:
                api_config["ignore_methods"].remove(method)
                persist_api_config()
                await event.edit(lang["api_ignore_removed"].format(method=method))
            else:
                await event.edit(lang["api_ignore_not_found"].format(method=method))

        elif subcmd == "clear":
            api_config["ignore_methods"] = []
            persist_api_config()
            await event.edit(lang["api_ignore_cleared"], parse_mode="html")

        else:
            await event.edit(lang["api_ignore_usage"], parse_mode="html")

    @kernel.register.command("api_status")
    async def api_status_handler(event):
        """Show current MCUB protection status."""
        if not _mcub_available:
            await event.edit(lang["mcub_not_supported"])
            return

        mode = api_config.get("mcub_mode", "safe")
        dry_run = api_config.get("mcub_dry_run", False)
        allowlist = api_config.get("mcub_allowlist", [])
        al_str = ", ".join(f"`{m}`" for m in allowlist) if allowlist else "—"

        await event.edit(
            lang["mcub_status"].format(
                mode=mode,
                dry=(
                    '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji>'
                    if dry_run
                    else '<tg-emoji emoji-id="5388785832956016892">❌</tg-emoji>'
                ),
                allowlist=al_str,
            ),
            parse_mode="html",
        )

    async def api_protection_callback_handler(event):
        nonlocal protection_enabled
        data = event.data

        if data == b"api_protection_yes":
            if _mcub_available:
                # Show mode selector as second step
                current_mode = api_config.get("mcub_mode", "safe")
                buttons = [
                    [
                        Button.inline(
                            "🥽 safe",
                            b"api_prot_mode_safe",
                        )
                    ],
                    [
                        Button.inline(
                            "🔬 strict",
                            b"api_prot_mode_strict",
                        )
                    ],
                    [
                        Button.inline(
                            "🤧 off",
                            b"api_prot_mode_off",
                        )
                    ],
                    [
                        Button.inline(
                            lang["mcub_mode_default"].format(mode=current_mode),
                            b"api_prot_mode_default",
                        )
                    ],
                ]
                await event.edit(
                    lang["mcub_choose_mode"], buttons=buttons, parse_mode="html"
                )
            else:
                # No MCUB — just enable, no mode step
                protection_enabled = api_config["enable_protection"] = True
                await event.edit(
                    f'<tg-emoji emoji-id="5368585403467048206">🪬</tg-emoji> {lang["api_protection_on"]}',
                    parse_mode="html",
                )
                persist_api_config()

        elif data == b"api_protection_no":
            protection_enabled = api_config["enable_protection"] = False
            await event.edit(
                f'<tg-emoji emoji-id="5368585403467048206">🪬</tg-emoji> {lang["api_protection_off"]}',
                parse_mode="html",
            )
            persist_api_config()

        elif data.startswith(b"api_prot_mode_"):
            chosen = data[len(b"api_prot_mode_") :].decode()

            if chosen == "default":
                mode = api_config.get("mcub_mode", "safe")
            else:
                mode = chosen
                api_config["mcub_mode"] = mode

            # Enable protection + apply mode
            protection_enabled = api_config["enable_protection"] = True
            _apply_mcub_mode(mode)
            try:
                client.clear_blocked_request_handler()
            except Exception:
                pass
            client.on_blocked_request(_mcub_violation_handler)
            persist_api_config()

            label = (
                f'<tg-emoji emoji-id="5368585403467048206">🪬</tg-emoji> '
                f"{lang['api_protection_on']} · "
                f"{lang['mcub_mode_set'].format(mode=mode, dry='')}"
            )
            await event.edit(label, parse_mode="html")

    kernel.register_callback_handler(
        b"api_protection_", api_protection_callback_handler
    )
    kernel.register_callback_handler(b"api_prot_mode_", api_protection_callback_handler)
