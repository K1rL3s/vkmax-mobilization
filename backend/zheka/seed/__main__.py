from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from zheka.config import load_config
from zheka.core.services.demo import DemoService
from zheka.di import make_container
from zheka.logger import setup_logger
from zheka.runner import run
from zheka.seed.demo import seed


async def main() -> None:
    config = load_config()
    setup_logger(config.log)
    container = make_container(config=config)
    try:
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            demo = await request_container.get(DemoService)
            if await seed(
                session,
                demo,
                Path(config.files.dir),
                datetime.now(UTC),
            ):
                await session.commit()
    finally:
        await container.close()


if __name__ == "__main__":
    run(main())
