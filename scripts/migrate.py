import asyncio

from app.schema_migrations import run_migrations


async def main() -> None:
    version = await run_migrations()
    print(f"BantuDulu schema migration complete. version={version}")


if __name__ == "__main__":
    asyncio.run(main())
