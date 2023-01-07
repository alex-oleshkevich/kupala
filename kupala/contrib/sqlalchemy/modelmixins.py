from sqlalchemy.orm import Mapped

from kupala.contrib.sqlalchemy.types import AutoCreatedAt, AutoUpdatedAt


class Timestamps:
    created_at: Mapped[AutoCreatedAt]
    updated_at: Mapped[AutoUpdatedAt]
