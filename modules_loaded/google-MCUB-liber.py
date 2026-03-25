# github: https://github.com/hairpin01/repo-MCUB-fork/liber/
# Channel: https://t.me/LinuxGram2
# -------------------- Meta data ---------------------------
# requires: googlesearch-python, duckduckgo-search
# author: @Hairpin00
# version: 2.0.0
# description: Google (Text) + DuckDuckGo (Images) search with pagination
# ----------------------- End ------------------------------

import uuid
from telethon import Button
from telethon.tl.types import InputWebDocument, DocumentAttributeImageSize
from googlesearch import search

try:
    from duckduckgo_search import DDGS

    DDG_AVAILABLE = True
except ImportError:
    DDG_AVAILABLE = False


def register(kernel):
    # --- CONFIG & ICONS ---
    ICON_GOOGLE = "https://kappa.lol/HCIjwW"
    ICON_IMG = "https://cdn-icons-png.flaticon.com/512/3342/3342137.png"
    ICON_ERROR = "https://kappa.lol/oO9x4z"

    def get_thumb(url, mime_type="image/jpeg"):
        return InputWebDocument(
            url=url,
            size=0,
            mime_type=mime_type,
            attributes=[DocumentAttributeImageSize(w=0, h=0)],
        )

    def format_google_msg(entry, index, total):
        return (
            f"🔍 <b>Google Search</b> [{index + 1}/{total}]\n\n"
            f"🌐 <a href='{entry.url}'><b>{entry.title}</b></a>\n"
            f"📝 <i>{entry.description}</i>\n\n"
            f"🔗 {entry.url}"
        )

    def format_img_msg(entry, index, total):
        return (
            f"🖼 <b>Image Search</b> [{index + 1}/{total}]\n"
            f"📝 <b>Title:</b> {entry['title']}\n"
            f"🔗 <a href='{entry['image']}'>Source Link</a>"
        )

    async def search_callback_handler(event):
        data = event.data.decode("utf-8")
        # data format: type_uid_page (e.g., google_12345_1 or img_12345_2)

        try:
            search_type, uid, page_str = data.split("_")
            page = int(page_str)
        except ValueError:
            return

        cache_key = f"{search_type}_res_{uid}"
        results = kernel.cache.get(cache_key)

        if not results:
            await event.answer("⚠️ Session expired. Search again.", alert=True)
            return

        total = len(results)
        if page < 0:
            page = total - 1
        if page >= total:
            page = 0

        if search_type == "google":
            text = format_google_msg(results[page], page, total)
            link = results[page].url
            buttons = [
                [
                    Button.inline("⬅️", f"google_{uid}_{page-1}".encode()),
                    Button.inline(
                        f"{page + 1}/{total}", f"google_{uid}_{page}".encode()
                    ),
                    Button.inline("➡️", f"google_{uid}_{page+1}".encode()),
                ],
                [Button.url("↗️ Open Link", link)],
            ]
            await event.edit(
                text, buttons=buttons, parse_mode="html", link_preview=False
            )

        elif search_type == "img":
            entry = results[page]
            text = format_img_msg(entry, page, total)
            # Try to show the image preview in the message update
            # Note: Editing media in inline query results is tricky, usually we just edit text/buttons
            # or we rely on the link preview to show the image.

            buttons = [
                [
                    Button.inline("⬅️", f"img_{uid}_{page-1}".encode()),
                    Button.inline(f"{page + 1}/{total}", f"img_{uid}_{page}".encode()),
                    Button.inline("➡️", f"img_{uid}_{page+1}".encode()),
                ],
                [Button.url("↗️ Full Size", entry["image"])],
            ]

            await event.edit(
                f"<a href='{entry['image']}'>&#8203;</a>" + text,
                buttons=buttons,
                parse_mode="html",
                link_preview=True,
            )

    kernel.register_callback_handler("google_", search_callback_handler)
    kernel.register_callback_handler("img_", search_callback_handler)

    async def universal_inline_handler(event):
        builder = event.builder
        raw_text = event.text.strip()  # e.g., "google cats" or "img cats"

        mode = "google"
        query = raw_text

        if raw_text.startswith("google "):
            mode = "google"
            query = raw_text[7:].strip()
        elif raw_text.startswith("img "):
            mode = "img"
            query = raw_text[4:].strip()

        results_list = []

        if not query:
            # Empty state
            thumb = get_thumb(ICON_GOOGLE if mode == "google" else ICON_IMG)
            results_list.append(
                builder.article(
                    "Search", text=f"Type to search in {mode}...", thumb=thumb
                )
            )
            await event.answer(results_list)
            return

        try:
            search_uid = str(uuid.uuid4())[:8]

            if mode == "google":
                search_res = list(search(query, num_results=10, advanced=True))

                if not search_res:
                    raise Exception("No results found.")

                kernel.cache.set(f"google_res_{search_uid}", search_res, ttl=600)
                first = search_res[0]
                total = len(search_res)

                text = format_google_msg(first, 0, total)
                buttons = [
                    [
                        Button.inline("⬅️", f"google_{search_uid}_{total-1}".encode()),
                        Button.inline(f"1/{total}", f"google_{search_uid}_0".encode()),
                        Button.inline("➡️", f"google_{search_uid}_1".encode()),
                    ],
                    [Button.url("↗️ Open Link", first.url)],
                ]

                results_list.append(
                    builder.article(
                        title=f"🔎 {query}",
                        text=text,
                        description=first.description[:50] + "...",
                        thumb=get_thumb(ICON_GOOGLE),
                        buttons=buttons,
                        link_preview=False,
                    )
                )

            elif mode == "img":

                if not DDG_AVAILABLE:
                    raise Exception("duckduckgo-search library not installed.")

                with DDGS() as ddgs:
                    img_res = list(ddgs.images(query, max_results=10))

                if not img_res:
                    raise Exception("No images found.")

                kernel.cache.set(f"img_res_{search_uid}", img_res, ttl=600)
                first = img_res[0]
                total = len(img_res)

                text = format_img_msg(first, 0, total)
                buttons = [
                    [
                        Button.inline("⬅️", f"img_{search_uid}_{total-1}".encode()),
                        Button.inline(f"1/{total}", f"img_{search_uid}_0".encode()),
                        Button.inline("➡️", f"img_{search_uid}_1".encode()),
                    ],
                    [Button.url("↗️ Full Size", first["image"])],
                ]

                results_list.append(
                    builder.article(
                        title=f"🖼 {query}",
                        text=f"<a href='{first['image']}'>&#8203;</a>" + text,
                        description="Click to view images",
                        thumb=get_thumb(first["thumbnail"]),
                        buttons=buttons,
                        parse_mode="html",
                        link_preview=True,
                    )
                )

        except Exception as e:
            thumb = get_thumb(ICON_ERROR)
            error_msg = f"<b>{mode.capitalize()} Error:</b> {str(e)}"
            results_list.append(
                builder.article(
                    "Error",
                    text=error_msg,
                    description=str(e),
                    thumb=thumb,
                    parse_mode="html",
                )
            )
            kernel.logger.error(f"Search Module Error: {e}")

        await event.answer(results_list)

    kernel.register_inline_handler("google", universal_inline_handler)
    kernel.register_inline_handler("img", universal_inline_handler)

    @kernel.register_command("google")
    # .google <query> - Text search
    async def google_cmd(event):
        args = event.text.split(maxsplit=1)
        if len(args) < 2:
            await event.edit("Usage: .google query")
            return
        query = args[1]
        success, _ = await kernel.inline_query_and_click(
            event.chat_id, f"google {query}"
        )
        if success:
            await event.delete()

    @kernel.register_command("img")
    # .img <query> - Image search
    async def img_cmd(event):

        args = event.text.split(maxsplit=1)
        if len(args) < 2:
            await event.edit("Usage: .img query")
            return
        query = args[1]
        success, _ = await kernel.inline_query_and_click(event.chat_id, f"img {query}")
        if success:
            await event.delete()
