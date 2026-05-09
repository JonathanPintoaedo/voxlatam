from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from core.config import settings

# Convertir URL a async
async_url = settings.database_url.replace(
    "postgresql://", "postgresql+asyncpg://"
)

engine = create_async_engine(
    async_url,
    echo=False,
    pool_pre_ping=True,       # Reconecta si la conexión está caída
    pool_recycle=300,         # Recicla conexiones cada 5 minutos
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
