from html.parser import HTMLParser
from html import escape as escape_html
from telethon.tl.types import (
    MessageEntityBold, MessageEntityItalic, MessageEntityCode,
    MessageEntityPre, MessageEntityTextUrl, MessageEntityUnderline,
    MessageEntityStrike, MessageEntityBlockquote, MessageEntityCustomEmoji
)

def _utf16_len(s: str) -> int:

    return len(s.encode("utf-16-le")) // 2

class MCUBHTMLParser(HTMLParser):

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = ""
        self.entities = []


        self._u16 = 0


        self._open = []


    def _append_text(self, s: str):
        if not s:
            return
        self.text += s
        du = _utf16_len(s)
        self._u16 += du

        for item in self._open:
            if item["grow"]:
                item["entity"].length += du

    def _open_entity(self, tag: str, entity, grow: bool = True):
        self._open.append({"tag": tag, "entity": entity, "grow": grow})

    def _close_entity(self, tag: str):

        for i in range(len(self._open) - 1, -1, -1):
            if self._open[i]["tag"] == tag:
                item = self._open.pop(i)
                ent = item["entity"]
                if getattr(ent, "length", 0) > 0:
                    self.entities.append(ent)
                return


    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs or [])


        if tag == "br":
            self._append_text("\n")
            return


        if tag in ("b", "strong"):
            self._open_entity(tag, MessageEntityBold(offset=self._u16, length=0))
            return

        if tag in ("i", "em"):
            self._open_entity(tag, MessageEntityItalic(offset=self._u16, length=0))
            return

        if tag == "u":
            self._open_entity(tag, MessageEntityUnderline(offset=self._u16, length=0))
            return

        if tag in ("s", "del"):
            self._open_entity(tag, MessageEntityStrike(offset=self._u16, length=0))
            return

        if tag == "blockquote":
            args = {}
            if "expandable" in attrs:
                args["collapsed"] = True
            self._open_entity(tag, MessageEntityBlockquote(offset=self._u16, length=0, **args))
            return

        if tag == "code":
            self._open_entity(tag, MessageEntityCode(offset=self._u16, length=0))
            return

        if tag == "pre":
            args = {"language": attrs.get("language", "")}
            self._open_entity(tag, MessageEntityPre(offset=self._u16, length=0, **args))
            return


        if tag == "a":
            href = attrs.get("href")
            if href:
                self._open_entity(tag, MessageEntityTextUrl(offset=self._u16, length=0, url=href))
            return

        if tag == "tg-emoji":
            emoji_id = attrs.get("emoji-id")
            try:
                document_id = int(emoji_id)
            except (TypeError, ValueError):
                return
            self._open_entity(tag, MessageEntityCustomEmoji(offset=self._u16, length=0, document_id=document_id))
            return


        if tag == "img":
            src = attrs.get("src", "")
            if src.startswith("tg://emoji?id="):
                try:
                    document_id = int(src.split("=", 1)[1])
                except (ValueError, IndexError):
                    return


                placeholder = attrs.get("alt") or "\u2060"
                start = self._u16
                self._append_text(placeholder)
                self.entities.append(
                    MessageEntityCustomEmoji(offset=start, length=_utf16_len(placeholder), document_id=document_id)
                )
            return

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_data(self, data):
        self._append_text(data)

    def handle_endtag(self, tag):
        self._close_entity(tag)

    def close(self):
        super().close()
        while self._open:
            item = self._open.pop()
            ent = item["entity"]
            if getattr(ent, "length", 0) > 0:
                self.entities.append(ent)

def parse_html(html_text: str):
    parser = MCUBHTMLParser()
    parser.feed(html_text or "")
    parser.close()

    parser.entities.sort(key=lambda e: (e.offset, -e.length))
    return parser.text, parser.entities
