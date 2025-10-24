import sys
import asyncio
import pathlib
# Ensure project root is on sys.path so sibling packages like `db` can be imported
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from db.session import AsyncSessionLocal
from db.models import User


async def main():
    async with AsyncSessionLocal() as session:
        # Eagerly load the `batch` relationship to avoid async lazy-loading
        # which can raise MissingGreenlet in simple scripts.
        result = await session.execute(select(User).options(selectinload(User.batch)))
        users = result.scalars().all()

        if not users:
            print("No users found.")
            return

        print(f"Found {len(users)} user(s):")
        for u in users:
            batch_name = u.batch.name if u.batch else None
            print(
                f"id={u.id} user_id={u.user_id} username={u.username} is_admin={u.is_admin} batch={batch_name} join_date={u.join_date}"
            )


if __name__ == '__main__':
    asyncio.run(main())
