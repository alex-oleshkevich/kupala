import dataclasses


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class SecurityScheme[P]:
    name: str
    principal_type: type[P]
    scopes: tuple[str, ...] = ()
