# github: https://github.com/hairpin01/repo-MCUB-fork/liber/
# Channel: https://t.me/LinuxGram2
# -------------------- Meta data ---------------------------
# requires: matplotlib
# author: nercymods
# version: 2.0.2
# description: en: Module for viewing the top list in chat / ru: Модуль просмотра топ-листа в чате
# ----------------------- End ------------------------------

import asyncio
import io
import warnings
from collections import defaultdict
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from telethon.tl.functions.messages import SearchRequest, GetHistoryRequest
from telethon.tl.types import InputMessagesFilterEmpty

plt.style.use("dark_background")


def register(kernel):
    client = kernel.client

    async def get_message_count_fast(chat_id, user_id):
        total_count = 0
        offset_id = 0
        limit = 100

        while True:
            history = await client(
                GetHistoryRequest(
                    peer=chat_id,
                    offset_id=offset_id,
                    offset_date=None,
                    add_offset=0,
                    limit=limit,
                    max_id=0,
                    min_id=0,
                    hash=0,
                )
            )

            if not history.messages:
                break

            for message in history.messages:
                if message.sender_id == user_id:
                    total_count += 1

            offset_id = history.messages[-1].id

            if len(history.messages) < limit:
                break

        return total_count

    def generate_gradient(start_color, end_color, n):
        cmap = LinearSegmentedColormap.from_list(
            "custom_gradient", [start_color, end_color], N=n
        )
        return [cmap(i) for i in np.linspace(0, 1, n)]

    @kernel.register.command("top")
    # ru: топ юзеров в чате / en: top users in chat
    async def top_handler(event):
        try:
            await event.edit("🕒 Message counting has started, please wait...")

            chat_type = "chat"
            if event.is_private:
                chat_type = "private"
                chat_id = event.chat_id
            else:
                chat_id = event.chat_id

            if chat_type == "chat":
                users = await client.get_participants(chat_id)
                users_dict = {
                    user.id: (user.username or user.first_name) for user in users
                }
                message_count = defaultdict(int)

                for user_id in users_dict:
                    result = await client(
                        SearchRequest(
                            peer=chat_id,
                            q="",
                            filter=InputMessagesFilterEmpty(),
                            from_id=user_id,
                            limit=0,
                            min_date=None,
                            max_date=None,
                            offset_id=0,
                            add_offset=0,
                            max_id=0,
                            min_id=0,
                            hash=0,
                        )
                    )
                    message_count[user_id] = result.count

                sorted_message_count = sorted(
                    message_count.items(), key=lambda item: item[1], reverse=True
                )
                top_users = sorted_message_count[:20]
                usernames = [
                    users_dict[user_id] or "Unknown" for user_id, _ in top_users
                ]
                counts = [count for _, count in top_users]

                if not usernames:
                    await event.edit("❌ No messages found.")
                    return

                fig, ax = plt.subplots(figsize=(10, 5))
                colors = generate_gradient("#8A2BE2", "#4B0082", len(usernames))
                bars = ax.barh(
                    usernames, counts, color=colors, edgecolor="black", linewidth=0.5
                )

                for bar in bars:
                    bar.set_alpha(0.8)
                    bar.set_hatch("///")

                ax.set_xlabel("Message count", fontsize=12, color="white")
                ax.set_title(
                    "Top users by message count", fontsize=14, color="white", pad=20
                )
                ax.invert_yaxis()

                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)
                ax.spines["left"].set_color("#8A2BE2")
                ax.spines["bottom"].set_color("#8A2BE2")

                ax.grid(True, linestyle="--", alpha=0.6, color="gray")

                for i, (bar, username) in enumerate(zip(bars, usernames)):
                    if i < 3:
                        bar.set_color("#FFD700")
                        ax.text(
                            bar.get_width() + 5,
                            bar.get_y() + bar.get_height() / 2,
                            f"#{i+1}",
                            va="center",
                            ha="left",
                            color="#FFD700",
                            fontsize=12,
                        )

                buf = io.BytesIO()
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore")
                    plt.savefig(buf, format="png", bbox_inches="tight", dpi=100)

                buf.seek(0)

                buf.name = "top_chart.png"

                chat = await event.get_chat()
                caption = f"💬 Top users in <b>{chat.title}:</b>\n"
                caption += "\n".join(
                    [
                        f"{i+1}. {user} - {count}"
                        for i, (user, count) in enumerate(zip(usernames, counts))
                    ]
                )

                await client.send_file(
                    event.chat_id,
                    buf,
                    caption=caption,
                    parse_mode="html",
                    force_document=False,
                )
                plt.close()
                await event.delete()

            else:
                me = await client.get_me()
                target = await client.get_entity(chat_id)

                my_count, their_count = await asyncio.gather(
                    get_message_count_fast(chat_id, me.id),
                    get_message_count_fast(chat_id, target.id),
                )

                message_counts = [
                    (me.first_name, my_count),
                    (target.first_name, their_count),
                ]
                sorted_message_counts = sorted(
                    message_counts, key=lambda item: item[1], reverse=True
                )

                usernames = [user for user, _ in sorted_message_counts]
                counts = [count for _, count in sorted_message_counts]

                fig, ax = plt.subplots(figsize=(10, 5))
                colors = generate_gradient("#8A2BE2", "#4B0082", len(usernames))
                bars = ax.barh(
                    usernames, counts, color=colors, edgecolor="black", linewidth=0.5
                )

                for bar in bars:
                    bar.set_alpha(0.8)
                    bar.set_hatch("///")

                ax.set_xlabel("Message count", fontsize=12, color="white")
                ax.set_title(
                    "Top users by message count", fontsize=14, color="white", pad=20
                )
                ax.invert_yaxis()

                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)
                ax.spines["left"].set_color("#8A2BE2")
                ax.spines["bottom"].set_color("#8A2BE2")

                ax.grid(True, linestyle="--", alpha=0.6, color="gray")

                for i, (bar, username) in enumerate(zip(bars, usernames)):
                    if i < 3:
                        bar.set_color("#FFD700")
                        ax.text(
                            bar.get_width() + 5,
                            bar.get_y() + bar.get_height() / 2,
                            f"#{i+1}",
                            va="center",
                            ha="left",
                            color="#FFD700",
                            fontsize=12,
                        )

                buf = io.BytesIO()
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore")
                    plt.savefig(buf, format="png", bbox_inches="tight", dpi=100)

                buf.seek(0)

                buf.name = "private_chart.png"

                caption = f"💬 Message count in private chat with <b>{target.first_name}:</b>\n"
                caption += "\n".join(
                    [f'"{user}" - {count}' for user, count in zip(usernames, counts)]
                )

                await client.send_file(
                    event.chat_id,
                    buf,
                    caption=caption,
                    parse_mode="html",
                    force_document=False,
                )
                plt.close()
                await event.delete()

        except Exception as e:
            await kernel.handle_error(e, source="top_handler", event=event)
            await event.edit("❌ Error occurred, check logs")
