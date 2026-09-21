from collections.abc import AsyncGenerator, AsyncIterable

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    close_all_sessions,
    create_async_engine,
)

from zheka.config import DbConfig


class DbProvider(Provider):
    @provide(scope=Scope.APP)
    async def engine(self, config: DbConfig) -> AsyncIterable[AsyncEngine]:
        engine = create_async_engine(
            url=config.url,
            pool_size=20,
            max_overflow=10,
            pool_recycle=3600,
            pool_timeout=30,
            echo=False,
        )
        yield engine
        await engine.dispose(close=True)

    @provide(scope=Scope.APP)
    async def sessionmaker(
        self,
        engine: AsyncEngine,
    ) -> AsyncIterable[async_sessionmaker[AsyncSession]]:
        maker = async_sessionmaker(
            bind=engine,
            autoflush=False,
            future=True,
            expire_on_commit=False,
        )
        yield maker
        await close_all_sessions()

    @provide(scope=Scope.REQUEST)
    async def session(
        self,
        maker: async_sessionmaker[AsyncSession],
    ) -> AsyncGenerator[AsyncSession, BaseException | None]:
        async with maker() as session:
            # коммитят решатели транзакции, здесь только страховочный откат.
            # dishka передает исключение через agen.asend(exc), значением, так
            # что try/except вокруг yield не сработал бы
            exception = yield session
            if exception is not None:
                await session.rollback()
