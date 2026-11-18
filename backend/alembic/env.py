
from logging.config import fileConfig

from alembic import context

from app.core.config import settings
from app.database.base import Base
# Reusing the existing engine
from app.database.connection import engine

# Importing the models registers all tables with Base.metadata.
import app.database.models  # noqa: F401


# Alembic configuration object.
config = context.config

# Configure logging using alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# SQLAlchemy metadata containing all nine models.
# This is how Alembic knows what your database schema is supposed to look like.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Generate SQL migrations without opening a database connection.
    """

    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations using an actual database connection.
    """

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
