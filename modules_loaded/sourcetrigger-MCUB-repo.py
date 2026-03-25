# author: @YouRooni && @Hairpin00 && @kozhura_ubezhishe_player_fly
# version: 1.1.0
# description: отправляет медиа или текст из канала в ответ на текстовые триггеры (пересылка)

import logging
import re
import asyncio
import json
import os
from telethon import events

logger = logging.getLogger(__name__)

TRIGGERS_FILE = "sourcetrigger_triggers.json"


def register(kernel):
    client = kernel.client

    kernel.config.setdefault("sourcetrigger_channel_id", None)
    kernel.config.setdefault("sourcetrigger_auto_parse", True)

    triggers = {}
    BATCH_SIZE = 200

    def save_triggers():
        try:
            with open(TRIGGERS_FILE, "w", encoding="utf-8") as f:
                json.dump(triggers, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"failed to save triggers: {e}")

    def load_triggers():
        nonlocal triggers
        try:
            if os.path.exists(TRIGGERS_FILE):
                with open(TRIGGERS_FILE, "r", encoding="utf-8") as f:
                    triggers = json.load(f)
        except Exception as e:
            logger.error(f"failed to load triggers: {e}")
            triggers = {}

    load_triggers()

    async def process_message_for_triggers(msg):
        if not msg or not getattr(msg, "text", None):
            return None

        trigger_def_msg = msg
        content_msg = msg

        if msg.is_reply:
            replied = await msg.get_reply_message()
            if replied:
                content_msg = replied
            else:
                return None

        text = trigger_def_msg.text.strip()
        first_line = text.split("\n", 1)[0].strip()
        ttype, trigger = None, None

        if re.match(r"^~{1,3}", first_line):
            if first_line.startswith("~~~"):
                content_after = first_line[3:].lstrip()
                if content_after.startswith("|"):
                    pattern = content_after[1:].strip()
                    if pattern:
                        try:
                            re.compile(pattern, re.IGNORECASE)
                            ttype, trigger = "regex_delete", pattern
                        except re.error:
                            pass
                else:
                    ttype, trigger = "exact_delete", content_after.strip().lower()
            elif first_line.startswith("~~"):
                ttype, trigger = "contains", first_line[2:].strip().lower()
            elif first_line.startswith("~"):
                content_after = first_line[1:].lstrip()
                if content_after.startswith("|"):
                    pattern = content_after[1:].strip()
                    if pattern:
                        try:
                            re.compile(pattern, re.IGNORECASE)
                            ttype, trigger = "regex", pattern
                        except re.error:
                            pass
                else:
                    ttype, trigger = "exact", content_after.strip().lower()

        if ttype and trigger:
            return ttype, trigger, content_msg.id
        return None

    async def process_batch(
        tasks, triggers_dict, counts_dict, status_msg, total_processed
    ):
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception) or not result:
                continue
            ttype, trigger, msg_id = result

            key = f"{ttype}::{trigger}"
            if key not in triggers_dict:
                triggers_dict[key] = []

            if msg_id not in triggers_dict[key]:
                triggers_dict[key].append(msg_id)

            counts_dict[ttype] += 1

        if status_msg and total_processed % (BATCH_SIZE * 5) == 0:
            try:
                await status_msg.edit(
                    f"☄️ обработка... обработано {total_processed} сообщений"
                )
            except Exception:
                pass

    async def run_parser(event=None):
        try:
            if event:
                status_msg = await event.edit("💎")
            else:
                status_msg = None

            triggers.clear()

            counts = {
                "exact": 0,
                "contains": 0,
                "exact_delete": 0,
                "regex": 0,
                "regex_delete": 0,
            }

            source_id = kernel.config.get("sourcetrigger_channel_id")
            if not source_id:
                if event:
                    await event.edit("❌ источник не настроен")
                return

            try:
                channel_entity = await client.get_entity(source_id)
                tasks = []
                processed_count = 0

                async for msg in client.iter_messages(channel_entity, limit=None):
                    tasks.append(asyncio.create_task(process_message_for_triggers(msg)))
                    processed_count += 1
                    if len(tasks) >= BATCH_SIZE:
                        await process_batch(
                            tasks, triggers, counts, status_msg, processed_count
                        )
                        tasks.clear()

                if tasks:
                    await process_batch(
                        tasks, triggers, counts, status_msg, processed_count
                    )

                save_triggers()

                if event:
                    await status_msg.edit(
                        f"👁‍🗨 индексация завершена!\n"
                        f"<blockquote>точных: {counts['exact']}\n"
                        f"по вхождению: {counts['contains']}\n"
                        f"точных+удалить: {counts['exact_delete']}\n"
                        f"regex: {counts['regex']}\n"
                        f"regex+удалить: {counts['regex_delete']}</blockquote>",
                        parse_mode="html",
                    )

            except Exception as e:
                logger.error(f"parse error: {e}")
                if event:
                    await event.edit(f"❌ ошибка: {str(e)[:100]}")
        except Exception as e:
            await kernel.handle_error(e, source="run_parser", event=event)

    if kernel.config.get("sourcetrigger_auto_parse"):

        async def auto_parse_startup():
            await asyncio.sleep(5)
            await run_parser()

        asyncio.create_task(auto_parse_startup())

    @kernel.register.command("parsetriggers")
    # обновить базу триггеров из канала
    async def parsetriggers_cmd(event):
        await run_parser(event)

    def parse_trigger_string(text):
        text = text.strip()
        ttype, trigger = None, None
        if text.startswith("~~~"):
            content_after = text[3:].lstrip()
            if content_after.startswith("|"):
                pattern = content_after[1:].strip()
                if pattern:
                    try:
                        re.compile(pattern, re.IGNORECASE)
                        ttype, trigger = "regex_delete", pattern
                    except re.error:
                        return None, None
            else:
                ttype, trigger = "exact_delete", content_after.strip().lower()
        elif text.startswith("~~"):
            ttype, trigger = "contains", text[2:].strip().lower()
        elif text.startswith("~"):
            content_after = text[1:].lstrip()
            if content_after.startswith("|"):
                pattern = content_after[1:].strip()
                if pattern:
                    try:
                        re.compile(pattern, re.IGNORECASE)
                        ttype, trigger = "regex", pattern
                    except re.error:
                        return None, None
            else:
                ttype, trigger = "exact", content_after.strip().lower()
        return ttype, trigger

    @kernel.register.command("addtrigger")
    # добавить новый триггер (ответ на сообщение + текст триггера)
    async def addtrigger_cmd(event):
        try:
            reply = await event.get_reply_message()
            if not reply:
                await event.edit("💎 нужно ответить на сообщение")
                return

            args = event.text.split(maxsplit=1)
            if len(args) < 2:
                await event.edit("📝 укажите триггер (например: ~привет)")
                return

            trigger_text = args[1].strip()
            ttype, trigger = parse_trigger_string(trigger_text)
            if not ttype or not trigger:
                await event.edit("❌ неверный формат триггера")
                return

            source_id = kernel.config.get("sourcetrigger_channel_id")
            if not source_id:
                await event.edit("❌ источник не настроен")
                return

            await event.edit("❄️")

            try:
                content_msg = await client.send_file(source_id, reply)
                trigger_msg = await client.send_message(
                    source_id, trigger_text, reply_to=content_msg.id
                )

                key = f"{ttype}::{trigger}"
                if key not in triggers:
                    triggers[key] = []

                if content_msg.id not in triggers[key]:
                    triggers[key].append(content_msg.id)

                save_triggers()

                await event.edit(
                    f"🪬 <b>Триггер</b> добавлен: <code>{trigger_text}</code>",
                    parse_mode="html",
                )
                await event.delete()
            except Exception as e:
                await event.edit(f"❌ ошибка: {str(e)[:100]}")
        except Exception as e:
            await kernel.handle_error(e, source="addtrigger_cmd", event=event)
            await event.edit("🌩️ <b>ошибка, смотри логи</b>", parse_mode="html")

    async def source_channel_watcher(event):
        try:
            source_id = kernel.config.get("sourcetrigger_channel_id")
            if not source_id:
                return

            if event.chat_id != source_id:
                return

            result = await process_message_for_triggers(event.message)
            if not result:
                return

            ttype, trigger, msg_id = result
            key = f"{ttype}::{trigger}"
            if key not in triggers:
                triggers[key] = []

            if msg_id not in triggers[key]:
                triggers[key].append(msg_id)

            save_triggers()
        except Exception as e:
            await kernel.handle_error(e, source="source_channel_watcher", event=event)

    client.on(events.NewMessage(func=lambda e: True))(source_channel_watcher)

    async def process_and_send(trigger_message, msg_id):
        try:
            source_id = kernel.config.get("sourcetrigger_channel_id")
            if not source_id:
                return

            source_msg = await client.get_messages(source_id, ids=msg_id)
            if not source_msg:
                return
            reply_to_id = (
                trigger_message.reply_to_msg_id if trigger_message.is_reply else None
            )

            await client.send_message(
                trigger_message.chat_id, source_msg, reply_to=reply_to_id
            )

            logger.debug(f"message {msg_id} forwarded to {trigger_message.chat_id}")

        except Exception as e:
            logger.error(f"forward error for {msg_id}: {e}")

    async def trigger_watcher(event):
        try:
            if not event.out or not event.text:
                return

            text = event.text
            low_text_stripped = text.strip().lower()

            matched_key = None

            for key in triggers:
                if key.startswith("regex_delete::"):
                    pattern = key.split("::", 1)[1]
                    try:
                        if re.fullmatch(pattern, text, re.IGNORECASE):
                            matched_key = key
                            break
                    except re.error:
                        continue

            if not matched_key:
                exact_delete_key = f"exact_delete::{low_text_stripped}"
                if exact_delete_key in triggers:
                    matched_key = exact_delete_key

            if not matched_key:
                for key in triggers:
                    if key.startswith("regex::"):
                        pattern = key.split("::", 1)[1]
                        try:
                            if re.fullmatch(pattern, text, re.IGNORECASE):
                                matched_key = key
                                break
                        except re.error:
                            continue

            if not matched_key:
                exact_key = f"exact::{low_text_stripped}"
                if exact_key in triggers:
                    matched_key = exact_key

            if not matched_key:
                for key in triggers:
                    if key.startswith("contains::"):
                        trigger = key.split("::", 1)[1]
                        if trigger in text.lower():
                            matched_key = key
                            break

            if matched_key:
                msg_ids = triggers[matched_key]
                if not msg_ids:
                    return

                should_delete = "delete" in matched_key.split("::", 1)[0]

                tasks = [process_and_send(event, msg_id) for msg_id in msg_ids]
                await asyncio.gather(*tasks)

                if should_delete and event.out:
                    await event.delete()
        except Exception as e:
            await kernel.handle_error(e, source="trigger_watcher", event=event)

    client.on(events.NewMessage(outgoing=True, func=lambda e: bool(e.text)))(
        trigger_watcher
    )
