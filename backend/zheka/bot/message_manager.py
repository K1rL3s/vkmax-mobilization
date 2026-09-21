from typing import cast

from maxo import Bot
from maxo.dialogs.api.entities import NewMessage
from maxo.dialogs.manager.message_manager import MessageManager
from maxo.omit import Omitted
from maxo.types import Attachments, AttachmentsRequests, Message

from zheka.infra.max.sender import dialog_notify


class ZhekaMessageManager(MessageManager):
    async def send_message(self, bot: Bot, new_message: NewMessage) -> Message:
        # копия maxo 0.9.0, где notify=True зашит константой. edit_message не
        # тронут: редактирование не звонит
        if new_message.link_preview_options:
            disable_link_preview = new_message.link_preview_options.is_disabled
        else:
            disable_link_preview = Omitted()

        attachments = await self._build_attachments(
            bot,
            new_message.keyboard,
            new_message.media,
        )
        recipient = new_message.recipient
        chat_id = Omitted() if recipient.chat_id is None else recipient.chat_id
        user_id = Omitted() if recipient.user_id is None else recipient.user_id
        result = await bot.send_message(
            chat_id=chat_id,
            user_id=user_id,
            text=new_message.text,
            link=new_message.link_to,
            notify=dialog_notify.get(),
            attachments=cast(
                list[AttachmentsRequests | Attachments],
                attachments,
            ),
            format=new_message.parse_mode,
            disable_link_preview=disable_link_preview,
        )
        await self._save_media_ids(new_message, result.message)
        return result.message
