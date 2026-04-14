# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

import uuid
from typing import Any, Optional


def build_inline_result_text(
    title: str,
    text: str,
    description: Optional[str] = None,
    parse_mode: str = "HTML",
    result_id: Optional[str] = None,
) -> dict[str, Any]:
    result = {
        "type": "article",
        "id": result_id or str(uuid.uuid4()),
        "title": title,
        "input_message_content": {
            "message_text": text or "",
            "parse_mode": parse_mode,
        },
    }
    if description is not None:
        result["description"] = description
    elif text:
        result["description"] = text[:200]
    return result


def build_inline_result_photo(
    photo_url: str,
    text: str,
    title: str,
    description: Optional[str] = None,
    parse_mode: str = "HTML",
    thumb_url: Optional[str] = None,
    result_id: Optional[str] = None,
) -> dict[str, Any]:
    result = {
        "type": "photo",
        "id": result_id or str(uuid.uuid4()),
        "photo_url": photo_url,
        "thumbnail_url": thumb_url or photo_url,
        "title": title,
        "caption": text,
        "parse_mode": parse_mode,
    }
    if description is not None:
        result["description"] = description
    return result


def build_inline_result_video(
    video_url: str,
    text: str,
    title: str,
    mime_type: str = "video/mp4",
    thumb_url: Optional[str] = None,
    description: Optional[str] = None,
    parse_mode: str = "HTML",
    result_id: Optional[str] = None,
) -> dict[str, Any]:
    result = {
        "type": "video",
        "id": result_id or str(uuid.uuid4()),
        "video_url": video_url,
        "mime_type": mime_type,
        "thumbnail_url": thumb_url or video_url,
        "title": title,
        "caption": text,
        "parse_mode": parse_mode,
    }
    if description is not None:
        result["description"] = description
    return result


def build_inline_result_document(
    document_url: str,
    text: str,
    title: str,
    mime_type: str = "application/octet-stream",
    thumb_url: Optional[str] = None,
    description: Optional[str] = None,
    parse_mode: str = "HTML",
    result_id: Optional[str] = None,
) -> dict[str, Any]:
    result = {
        "type": "document",
        "id": result_id or str(uuid.uuid4()),
        "document_url": document_url,
        "mime_type": mime_type,
        "thumbnail_url": thumb_url or "https://kappa.lol/KSKoOu",
        "title": title,
        "caption": text,
        "parse_mode": parse_mode,
    }
    if description is not None:
        result["description"] = description
    return result


def build_inline_result_gif(
    gif_url: str,
    text: str,
    title: str,
    thumb_url: Optional[str] = None,
    description: Optional[str] = None,
    parse_mode: str = "HTML",
    result_id: Optional[str] = None,
) -> dict[str, Any]:
    result = {
        "type": "mpeg4_gif",
        "id": result_id or str(uuid.uuid4()),
        "mpeg4_url": gif_url,
        "thumbnail_url": thumb_url or gif_url,
        "title": title,
        "caption": text,
        "parse_mode": parse_mode,
    }
    if description is not None:
        result["description"] = description
    return result


def build_inline_result_media(
    media_url: str,
    media_type: str,
    text: str,
    title: str,
    description: Optional[str] = None,
    parse_mode: str = "HTML",
    result_id: Optional[str] = None,
) -> dict[str, Any]:
    media_type = media_type.lower()

    if media_type == "photo":
        return build_inline_result_photo(
            photo_url=media_url,
            text=text,
            title=title,
            description=description,
            parse_mode=parse_mode,
            result_id=result_id,
        )
    elif media_type == "video":
        return build_inline_result_video(
            video_url=media_url,
            text=text,
            title=title,
            description=description,
            parse_mode=parse_mode,
            result_id=result_id,
        )
    elif media_type == "gif":
        return build_inline_result_gif(
            gif_url=media_url,
            text=text,
            title=title,
            description=description,
            parse_mode=parse_mode,
            result_id=result_id,
        )
    elif media_type == "document":
        return build_inline_result_document(
            document_url=media_url,
            text=text,
            title=title,
            description=description,
            parse_mode=parse_mode,
            result_id=result_id,
        )
    elif media_type == "audio":
        return build_inline_result_audio(
            audio_url=media_url,
            text=text,
            title=title,
            description=description,
            parse_mode=parse_mode,
            result_id=result_id,
        )
    elif media_type == "voice":
        return build_inline_result_voice(
            voice_url=media_url,
            text=text,
            title=title,
            description=description,
            parse_mode=parse_mode,
            result_id=result_id,
        )
    elif media_type == "sticker":
        return build_inline_result_sticker(
            sticker_url=media_url,
            text=text,
            title=title,
            description=description,
            parse_mode=parse_mode,
            result_id=result_id,
        )
    else:
        return build_inline_result_photo(
            photo_url=media_url,
            text=text,
            title=title,
            description=description,
            parse_mode=parse_mode,
            result_id=result_id,
        )


def build_inline_result_poll(
    question: str,
    options: list[str],
    title: str,
    description: Optional[str] = None,
    is_multiple: bool = False,
    correct_option: Optional[int] = None,
) -> dict[str, Any]:
    result = {
        "type": "poll",
        "id": str(uuid.uuid4()),
        "title": title,
        "poll": {
            "question": question,
            "options": [{"text": opt} for opt in options],
        },
    }
    if description is not None:
        result["description"] = description
    if is_multiple:
        result["poll"]["allow_multiple_answers"] = True
    if correct_option is not None:
        result["poll"]["correct_option_id"] = correct_option
    return result


def build_inline_result_location(
    latitude: float,
    longitude: float,
    title: str,
    description: Optional[str] = None,
    result_id: Optional[str] = None,
) -> dict[str, Any]:
    result = {
        "type": "location",
        "id": result_id or str(uuid.uuid4()),
        "latitude": latitude,
        "longitude": longitude,
        "title": title,
    }
    if description is not None:
        result["description"] = description
    return result


def build_inline_result_venue(
    latitude: float,
    longitude: float,
    title: str,
    address: str,
    provider: Optional[str] = None,
    venue_id: Optional[str] = None,
    venue_type: Optional[str] = None,
    description: Optional[str] = None,
    result_id: Optional[str] = None,
) -> dict[str, Any]:
    result = {
        "type": "venue",
        "id": result_id or str(uuid.uuid4()),
        "latitude": latitude,
        "longitude": longitude,
        "title": title,
        "address": address,
    }
    if provider is not None:
        result["provider"] = provider
    if venue_id is not None:
        result["venue_id"] = venue_id
    if venue_type is not None:
        result["venue_type"] = venue_type
    if description is not None:
        result["description"] = description
    return result


def build_inline_result_contact(
    phone_number: str,
    first_name: str,
    last_name: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    result_id: Optional[str] = None,
) -> dict[str, Any]:
    result = {
        "type": "contact",
        "id": result_id or str(uuid.uuid4()),
        "phone_number": phone_number,
        "first_name": first_name,
    }
    if last_name is not None:
        result["last_name"] = last_name
    if title is not None:
        result["title"] = title
    if description is not None:
        result["description"] = description
    return result


def build_inline_result_audio(
    audio_url: str,
    text: str,
    title: str,
    performer: Optional[str] = None,
    duration: Optional[int] = None,
    description: Optional[str] = None,
    parse_mode: str = "HTML",
    result_id: Optional[str] = None,
) -> dict[str, Any]:
    result = {
        "type": "audio",
        "id": result_id or str(uuid.uuid4()),
        "audio_url": audio_url,
        "title": title,
        "caption": text,
        "parse_mode": parse_mode,
    }
    if performer is not None:
        result["performer"] = performer
    if duration is not None:
        result["audio_duration"] = duration
    if description is not None:
        result["description"] = description
    return result


def build_inline_result_voice(
    voice_url: str,
    text: str,
    title: str,
    duration: Optional[int] = None,
    description: Optional[str] = None,
    parse_mode: str = "HTML",
    result_id: Optional[str] = None,
) -> dict[str, Any]:
    result = {
        "type": "voice",
        "id": result_id or str(uuid.uuid4()),
        "voice_url": voice_url,
        "title": title,
        "caption": text,
        "parse_mode": parse_mode,
    }
    if duration is not None:
        result["voice_duration"] = duration
    if description is not None:
        result["description"] = description
    return result


def build_inline_result_sticker(
    sticker_url: str,
    text: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    result_id: Optional[str] = None,
) -> dict[str, Any]:
    result = {
        "type": "sticker",
        "id": result_id or str(uuid.uuid4()),
        "sticker_url": sticker_url,
    }
    if text is not None:
        result["caption"] = text
    if title is not None:
        result["title"] = title
    if description is not None:
        result["description"] = description
    return result


def build_inline_result_game(
    game_short_name: str,
    title: str,
    description: Optional[str] = None,
    text: Optional[str] = None,
    result_id: Optional[str] = None,
) -> dict[str, Any]:
    result = {
        "type": "game",
        "id": result_id or str(uuid.uuid4()),
        "game_short_name": game_short_name,
        "title": title,
    }
    if description is not None:
        result["description"] = description
    return result


def build_inline_result_article(
    title: str,
    text: str,
    url: Optional[str] = None,
    hide_url: bool = False,
    description: Optional[str] = None,
    thumb_url: Optional[str] = None,
    parse_mode: str = "HTML",
) -> dict[str, Any]:
    result = {
        "type": "article",
        "id": str(uuid.uuid4()),
        "title": title,
        "input_message_content": {
            "message_text": text or "",
            "parse_mode": parse_mode,
        },
    }
    if url is not None:
        result["url"] = url
        result["hide_url"] = hide_url
    if description is not None:
        result["description"] = description
    elif text:
        result["description"] = text[:200]
    if thumb_url is not None:
        result["thumbnail_url"] = thumb_url
    return result
