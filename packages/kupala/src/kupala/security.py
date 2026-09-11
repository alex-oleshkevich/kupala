import dataclasses


@dataclasses.dataclass(frozen=True, slots=True)
class Identity[T]:
    """An authenticated principal and the scopes granted to it."""

    principal: T
    scopes: frozenset[str] = dataclasses.field(default_factory=frozenset)
