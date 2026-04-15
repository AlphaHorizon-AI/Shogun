import asyncio
from shogun.db.session import SessionLocal
from sqlalchemy import text

async def check_roles():
    async with SessionLocal() as session:
        result = await session.execute(text("SELECT id, name, slug FROM samurai_roles"))
        roles = result.all()
        print(f"Total roles found: {len(roles)}")
        for r in roles:
            print(f"- {r.name} ({r.slug})")

if __name__ == "__main__":
    asyncio.run(check_roles())
