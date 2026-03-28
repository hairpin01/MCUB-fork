import uuid
from typing import Any, Optional


def build_inline_result_text(
    title: str,
    text: str,
    description: Optional[str] = None,
    parse_mode: str = "HTML",
) -> dict[str, Any]:
    return {
        "type": "article",
        "id": str(uuid.uuid4()),
        "title": title,
        "description": description or text[:200],
        "input_message_content": {
            "message_text": text,
            "parse_mode": parse_mode,
        },
    }


def build_inline_result_photo(
    photo_url: str,
    text: str,
    title: str,
    description: Optional[str] = None,
    parse_mode: str = "HTML",
    thumb_url: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "type": "photo",
        "id": str(uuid.uuid4()),
        "photo_url": photo_url,
        "thumb_url": thumb_url or photo_url,
        "title": title,
        "description": description,
        "caption": text,
        "parse_mode": parse_mode,
    }


def build_inline_result_video(
    video_url: str,
    text: str,
    title: str,
    mime_type: str = "video/mp4",
    thumb_url: Optional[str] = None,
    description: Optional[str] = None,
    parse_mode: str = "HTML",
) -> dict[str, Any]:
    return {
        "type": "video",
        "id": str(uuid.uuid4()),
        "video_url": video_url,
        "mime_type": mime_type,
        "thumb_url": thumb_url or video_url,
        "title": title,
        "description": description,
        "caption": text,
        "parse_mode": parse_mode,
    }


def build_inline_result_document(
    document_url: str,
    text: str,
    title: str,
    mime_type: str = "application/octet-stream",
    thumb_url: Optional[str] = None,
    description: Optional[str] = None,
    parse_mode: str = "HTML",
) -> dict[str, Any]:
    return {
        "type": "document",
        "id": str(uuid.uuid4()),
        "document_url": document_url,
        "mime_type": mime_type,
        "thumb_url": thumb_url or "https://kappa.lol/KSKoOu",
        "title": title,
        "description": description,
        "caption": text,
        "parse_mode": parse_mode,
    }


def build_inline_result_gif(
    gif_url: str,
    text: str,
    title: str,
    thumb_url: Optional[str] = None,
    description: Optional[str] = None,
    parse_mode: str = "HTML",
) -> dict[str, Any]:
    return {
        "type": "mpeg4_gif",
        "id": str(uuid.uuid4()),
        "mpeg4_url": gif_url,
        "thumb_url": thumb_url or gif_url,
        "title": title,
        "description": description,
        "caption": text,
        "parse_mode": parse_mode,
    }


def build_inline_result_media(
    media_url: str,
    media_type: str,
    text: str,
    title: str,
    description: Optional[str] = None,
    parse_mode: str = "HTML",
) -> dict[str, Any]:
    media_type = media_type.lower()

    if media_type == "photo":
        return build_inline_result_photo(
            photo_url=media_url,
            text=text,
            title=title,
            description=description,
            parse_mode=parse_mode,
        )
    elif media_type == "video":
        return build_inline_result_video(
            video_url=media_url,
            text=text,
            title=title,
            description=description,
            parse_mode=parse_mode,
        )
    elif media_type == "gif":
        return build_inline_result_gif(
            gif_url=media_url,
            text=text,
            title=title,
            description=description,
            parse_mode=parse_mode,
        )
    elif media_type == "document":
        return build_inline_result_document(
            document_url=media_url,
            text=text,
            title=title,
            description=description,
            parse_mode=parse_mode,
        )
    else:
        return build_inline_result_photo(
            photo_url=media_url,
            text=text,
            title=title,
            description=description,
            parse_mode=parse_mode,
        )
