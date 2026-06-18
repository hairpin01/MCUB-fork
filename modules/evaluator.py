# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

import asyncio
import html
import io
import os
import tempfile
import time
import traceback
from typing import Any

from telethon import events

import core.lib.loader.module_base as loader
from core.lib.loader.module_base import ModuleBase, command
from core.lib.utils.logger import ErrorFormatter
from utils.strings import Strings

CUSTOM_EMOJI = {
    "🧿": '<tg-emoji emoji-id="5426900601101374618">🧿</tg-emoji>',
    "❌": '<tg-emoji emoji-id="5388785832956016892">❌</tg-emoji>',
    "🧬": '<tg-emoji emoji-id="5368513458469878442">🧬</tg-emoji>',
    "💠": '<tg-emoji emoji-id="5404366668635865453">💠</tg-emoji>',
}

LANG_EMOJI = {
    "py": '<tg-emoji emoji-id="5300928913956938544">💻</tg-emoji>',
    "js": '<tg-emoji emoji-id="5301114585393144059">💻</tg-emoji>',
    "rb": '<tg-emoji emoji-id="5303402295428390127">💻</tg-emoji>',
    "go": '<tg-emoji emoji-id="5300888829027165969">💻</tg-emoji>',
    "rs": '<tg-emoji emoji-id="5301209568594894358">💻</tg-emoji>',
}


class EvalModule(ModuleBase):
    name = "evaluator"
    version = "1.1.0"
    author = "@hairpin00"
    description = {
        "ru": "Выпoлнeниe Python, JS, Ruby, Go, Rust кoдa",
        "en": "Execute Python, JS, Ruby, Go, Rust code",
    }

    strings: dict | Strings = {"name": "eval"}

    @command(
        "py",
        doc_ru="<кoд> выпoлнить Python кoд",
        doc_en="<code> execute Python code",
    )
    async def cmd_py(self, event: events.NewMessage.Event) -> None:
        code = html.unescape(self.args_raw(event).strip()).replace("\u00a0", " ")
        pipe_input = getattr(event, "pipe_input", None) or ""

        if not code and pipe_input:
            code = pipe_input

        start_time = time.time()

        # Use a per-invocation buffer.  Do NOT replace sys.stdout globally -
        # that is not concurrency-safe: two concurrent .py commands would share
        # or swap each other's buffers, and an unhandled exception before the
        # restore line would permanently silence all logging.
        output = io.StringIO()

        me = await self.client.get_me()
        m = event
        bot = self.kernel.bot_client
        reply = await m.get_reply_message()
        r_text = html.unescape(self.kernel.raw_text(reply))

        local_vars: dict[str, Any] = {
            "loader": loader,
            "self": self,
            "r_text": r_text,
            "r": reply,
            "c": self.client,
            "m": m,
            "me": me,
            "start_time": start_time,
            "kernel": self.kernel,
            "k": self.kernel,
            "client": self.client,
            "bot": bot,
            "event": event,
            "utils": __import__("utils"),
            "asyncio": __import__("asyncio"),
            "telethon": __import__("telethon"),
            "Button": __import__("telethon").Button,
            "events": __import__("telethon").events,
            "pipe_input": pipe_input,
            "_": pipe_input,
        }

        _tb_raw: str | None = None
        import contextlib

        stdout_text = ""
        return_val = None
        try:
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                exec(
                    "async def __exec():\n    " + "\n    ".join(code.split("\n")),
                    local_vars,
                )
                return_val = await local_vars["__exec"]()
            stdout_text = output.getvalue()
        except Exception:
            _tb_raw = traceback.format_exc()

        end_time = time.time()
        elapsed = round((end_time - start_time) * 1000, 2)

        s = self.strings

        if _tb_raw:
            _tb_clean = _tb_raw.replace("Traceback (most recent call last):\n", "", 1)
            _tb_lines = [l for l in _tb_clean.split("\n") if l]
            if len(_tb_lines) > 1:
                stack_part = "\n".join(_tb_lines[:-1])
                error_part = _tb_lines[-1]
                result_text = ErrorFormatter.format_full_traceback(stack_part) + "\n"
            else:
                error_part = _tb_lines[0] if _tb_lines else "Unknown error"
                result_text = ""
            result_text += (
                f'{CUSTOM_EMOJI["❌"]} <code>{html.escape(error_part)}</code>'
            )
            result_header = s["result_header_error"]
        elif stdout_text and return_val is not None:
            result_text = stdout_text + (
                "\n" + str(return_val) if return_val is not None else ""
            )
            result_header = s["result_header_executed"]
        elif stdout_text:
            result_text = stdout_text
            result_header = s["result_header_stdout"]
        elif return_val is not None:
            result_text = str(return_val)
            result_header = s["result_header_return"]
        else:
            result_text = ""
            result_header = s["result_header_empty"]

        code_display = html.escape(code[:1000]) + ("..." if len(code) > 1000 else "")

        if getattr(event, "piped", False):
            event.pipe_output = _tb_raw or result_text
            return

        if len(result_text) > 4000:
            file_content = _tb_raw or result_text
            result_file = io.BytesIO(file_content.encode("utf-8", errors="replace"))
            result_file.name = "eval_result.txt"

            response = f"""{LANG_EMOJI["py"]} <b>{s["code"]}</b>
<blockquote expandable><code>{code_display}</code></blockquote>
{CUSTOM_EMOJI["🧬"]} <b>{s["result_file"]}</b>
<blockquote>{CUSTOM_EMOJI["💠"]} <i>{s["executed_in"]}</i> <code>{elapsed}{s["ms"]}</code></blockquote>"""
            try:
                await self.edit(
                    event, response, file=result_file, as_html=True, force_document=True
                )
            except Exception:
                try:
                    result_file.seek(0)
                except Exception:
                    pass
                try:
                    await self.client.send_file(
                        event.chat_id,
                        file=result_file,
                        caption=response,
                        parse_mode="html",
                        reply_to=event.id,
                        force_document=True,
                    )
                except Exception:
                    try:
                        await self.edit(event, response, as_html=True)
                    except Exception:
                        pass
        else:
            if _tb_raw:
                result_block = f"<blockquote expandable>{result_text}</blockquote>"
            else:
                result_block = f"<blockquote expandable><code>{html.escape(result_text)}</code></blockquote>"
            response = f"""{LANG_EMOJI["py"]} <b>{s["code"]}</b>
<blockquote expandable><code>{code_display}</code></blockquote>
{CUSTOM_EMOJI["🧬"]} <b>{result_header}</b>
{result_block}
<blockquote>{CUSTOM_EMOJI["💠"]} <i>{s["executed_in"]}</i> <code>{elapsed}{s["ms"]}</code></blockquote>"""
            try:
                await self.edit(event, response, as_html=True)
            except Exception:
                pass

    async def _run_subprocess(
        self, code: str, cmd: list[str], ext: str, lang_name: str, timeout: int = 30
    ) -> tuple[str, str | None, float]:
        code = html.unescape(code).replace("\u00a0", " ")
        start = time.time()
        tmp = tempfile.NamedTemporaryFile(
            suffix=ext, mode="w", delete=False, encoding="utf-8"
        )
        try:
            tmp.write(code)
            tmp.close()

            if lang_name == "Rust":
                exe = tmp.name + ".bin"
                compile_proc = await asyncio.create_subprocess_exec(
                    "rustc",
                    tmp.name,
                    "-o",
                    exe,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    _, cerr = await asyncio.wait_for(
                        compile_proc.communicate(), timeout=timeout
                    )
                except TimeoutError:
                    compile_proc.kill()
                    await compile_proc.wait()
                    elapsed = round((time.time() - start) * 1000, 2)
                    return "", f"⏱ rustc timeout ({timeout}s)", elapsed
                cerr_text = cerr.decode("utf-8", errors="replace").strip()
                if compile_proc.returncode != 0:
                    elapsed = round((time.time() - start) * 1000, 2)
                    try:
                        os.unlink(exe)
                    except Exception:
                        pass
                    return "", cerr_text or "Rust compilation failed", elapsed
                if not os.path.isfile(exe):
                    elapsed = round((time.time() - start) * 1000, 2)
                    try:
                        os.unlink(exe)
                    except Exception:
                        pass
                    return "", "Rust compilation produced no binary", elapsed
                proc = await asyncio.create_subprocess_exec(
                    exe,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                full_cmd = [*cmd, tmp.name]
                proc = await asyncio.create_subprocess_exec(
                    *full_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except TimeoutError:
                proc.kill()
                await proc.wait()
                elapsed = round((time.time() - start) * 1000, 2)
                return "", f"⏱ Timeout ({timeout}s)", elapsed
            elapsed = round((time.time() - start) * 1000, 2)
            out = stdout.decode("utf-8", errors="replace").strip()
            err = stderr.decode("utf-8", errors="replace").strip()
            if lang_name == "Rust":
                try:
                    os.unlink(exe)
                except Exception:
                    pass
            if proc.returncode != 0 and err:
                return out or "", err, elapsed
            if out:
                return out, None, elapsed
            if err:
                return "", err, elapsed
            return "[done]", None, elapsed
        except FileNotFoundError:
            elapsed = round((time.time() - start) * 1000, 2)
            return "", self.strings("not_installed", lang=lang_name), elapsed
        except Exception as e:
            elapsed = round((time.time() - start) * 1000, 2)
            return "", str(e), elapsed
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass

    async def _format_subprocess_output(
        self,
        event: events.NewMessage.Event,
        code: str,
        output: str,
        error: str | None,
        elapsed: float,
        lang_key: str,
    ) -> None:
        lang_emoji = LANG_EMOJI.get(lang_key, CUSTOM_EMOJI["💠"])
        s = self.strings

        if error:
            result_text = f'{CUSTOM_EMOJI["❌"]} <code>{html.escape(error)}</code>'
            result_header = s["result_header_error"]
        elif output:
            result_text = (
                f"<code>{html.escape(output[:3000])}</code>"
                if len(output) < 4000
                else output
            )
            result_header = s["result_header_output"]
        else:
            result_text = ""
            result_header = s["result_header_empty"]

        code_display = html.escape(code[:1000]) + ("..." if len(code) > 1000 else "")

        if len(str(result_text)) > 4000:
            file_content = error or output
            fio = io.BytesIO(file_content.encode("utf-8", errors="replace"))
            fio.name = "result.txt"
            response = f"""{lang_emoji} <b>{s["code"]}</b>
<blockquote expandable><code>{code_display}</code></blockquote>
{CUSTOM_EMOJI["🧬"]} <b>{s["result_file"]}</b>
<blockquote>{CUSTOM_EMOJI["💠"]} <i>{s["executed_in"]}</i> <code>{elapsed}{s["ms"]}</code></blockquote>"""
            try:
                await self.edit(
                    event, response, file=fio, as_html=True, force_document=True
                )
            except Exception:
                try:
                    await self.client.send_file(
                        event.chat_id,
                        file=fio,
                        caption=response,
                        parse_mode="html",
                        reply_to=event.id,
                        force_document=True,
                    )
                except Exception:
                    pass
        else:
            if error:
                result_block = f"<blockquote expandable>{result_text}</blockquote>"
            else:
                result_block = f"<blockquote expandable><code>{html.escape(output)}</code></blockquote>"
            response = f"""{lang_emoji} <b>{s["code"]}</b>
<blockquote expandable><code>{code_display}</code></blockquote>
{CUSTOM_EMOJI["🧬"]} <b>{result_header}</b>
{result_block}
<blockquote>{CUSTOM_EMOJI["💠"]} <i>{s["executed_in"]}</i> <code>{elapsed}{s["ms"]}</code></blockquote>"""
            try:
                await self.edit(event, response, as_html=True)
            except Exception:
                pass

    async def _handle_piped(
        self, event, code: str, out: str, err, elapsed, lang: str, tb_raw=None
    ) -> bool:
        piped = getattr(event, "piped", False)
        if not piped:
            return False
        result = out if not err else err
        event.pipe_output = tb_raw or result
        return True

    @command(
        "js",
        doc_en="<code> execute JavaScript (Node.js) code",
        doc_ru="<кoд> выпoлнить JavaScript (Node.js) кoд",
    )
    async def cmd_js(self, event: events.NewMessage.Event) -> None:
        code = self.args_raw(event).strip()
        pipe_input = getattr(event, "pipe_input", None) or ""
        if not code and pipe_input:
            code = pipe_input
        if not code:
            await self.edit(event, f'❌ {self.strings("usage_js")}', parse_mode="html")
            return
        out, err, elapsed = await self._run_subprocess(
            code, ["node"], ".js", self.strings("lang_js")
        )
        if await self._handle_piped(event, code, out, err, elapsed, "js"):
            return
        await self._format_subprocess_output(event, code, out, err, elapsed, "js")

    @command(
        "rb",
        doc_en="<code> execute Ruby code",
        doc_ru="<кoд> выпoлнить Ruby кoд",
    )
    async def cmd_rb(self, event: events.NewMessage.Event) -> None:
        code = self.args_raw(event).strip()
        pipe_input = getattr(event, "pipe_input", None) or ""
        if not code and pipe_input:
            code = pipe_input
        if not code:
            await self.edit(event, f'❌ {self.strings("usage_rb")}', parse_mode="html")
            return
        out, err, elapsed = await self._run_subprocess(
            code, ["ruby"], ".rb", self.strings("lang_rb")
        )
        if await self._handle_piped(event, code, out, err, elapsed, "rb"):
            return
        await self._format_subprocess_output(event, code, out, err, elapsed, "rb")

    @command(
        "go",
        doc_en="<code> execute Go code",
        doc_ru="<кoд> выпoлнить Go кoд",
    )
    async def cmd_go(self, event: events.NewMessage.Event) -> None:
        code = self.args_raw(event).strip()
        pipe_input = getattr(event, "pipe_input", None) or ""
        if not code and pipe_input:
            code = pipe_input
        if not code:
            await self.edit(event, f'❌ {self.strings("usage_go")}', parse_mode="html")
            return
        out, err, elapsed = await self._run_subprocess(
            code, ["go", "run"], ".go", self.strings("lang_go")
        )
        if await self._handle_piped(event, code, out, err, elapsed, "go"):
            return
        await self._format_subprocess_output(event, code, out, err, elapsed, "go")

    @command(
        "rs",
        doc_en="<code> execute Rust code",
        doc_ru="<кoд> выпoлнить Rust кoд",
    )
    async def cmd_rs(self, event: events.NewMessage.Event) -> None:
        code = self.args_raw(event).strip()
        pipe_input = getattr(event, "pipe_input", None) or ""
        if not code and pipe_input:
            code = pipe_input
        if not code:
            await self.edit(event, f'❌ {self.strings("usage_rs")}', parse_mode="html")
            return
        out, err, elapsed = await self._run_subprocess(
            code, ["rustc"], ".rs", self.strings("lang_rs")
        )
        if await self._handle_piped(event, code, out, err, elapsed, "rs"):
            return
        await self._format_subprocess_output(event, code, out, err, elapsed, "rs")
