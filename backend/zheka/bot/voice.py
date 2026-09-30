from typing import Any

from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName

VOICE_PENDING = "⏳ Разбираю голосовое"
VOICE_FAILED = "🎤 Не разобрал голосовое, напишите текстом"


def publish_transcription(
    publisher: TaskPublisher,
    user_id: int,
    mid: str,
    draft: dict[str, Any],
    *,
    in_draft: bool,
) -> None:
    publisher.publish(
        TaskName.TRANSCRIBE_VOICE,
        user_id=user_id,
        mid=mid,
        draft=draft,
        in_draft=in_draft,
    )
