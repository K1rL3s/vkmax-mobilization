from typing import Any

from dishka import AsyncContainer
from dishka.integrations.taskiq import CONTAINER_ID, CONTAINER_REGISTRY
from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import TaskiqMessage, TaskiqMiddleware, TaskiqResult

from zheka.broker.publisher import TaskPublisher
from zheka.logger.context import task_id, task_name


class ContextVarsMiddleware(TaskiqMiddleware):
    def pre_execute(self, message: TaskiqMessage) -> TaskiqMessage:
        task_id.set(message.task_id)
        task_name.set(message.task_name)
        return message


class CommitMiddleware(TaskiqMiddleware):
    async def post_execute(
        self, message: TaskiqMessage, result: TaskiqResult[Any]
    ) -> None:
        if result.is_err:
            return
        container = self._container(message)
        session = await container.get(AsyncSession)
        await session.commit()
        # задачи, поставленные этой задачей, уезжают после ее коммита
        publisher = await container.get(TaskPublisher)
        await publisher.flush()

    async def on_error(
        self,
        message: TaskiqMessage,
        result: TaskiqResult[Any],
        exception: BaseException,
    ) -> None:
        session = await self._container(message).get(AsyncSession)
        await session.rollback()

    def _container(self, message: TaskiqMessage) -> AsyncContainer:
        container_id = message.labels[CONTAINER_ID]
        registry: dict[int, AsyncContainer] = self.broker.state[CONTAINER_REGISTRY]
        return registry[container_id]
