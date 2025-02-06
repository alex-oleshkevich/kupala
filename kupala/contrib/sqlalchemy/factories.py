import typing

import sqlalchemy as sa
from factory import enums, errors
from factory.alchemy import SESSION_PERSISTENCE_COMMIT, SESSION_PERSISTENCE_FLUSH, SQLAlchemyOptions
from factory.base import Factory, FactoryMetaClass, StubObject, T
from factory.errors import UnknownStrategy


class AsyncFactoryMetaClass(FactoryMetaClass):  # type: ignore[misc]
    async def __call__(cls, **kwargs: typing.Any) -> T | StubObject:  # noqa: ANN401,N805
        if cls._meta.strategy == enums.BUILD_STRATEGY:
            return cls.build(**kwargs)

        if cls._meta.strategy == enums.CREATE_STRATEGY:
            return await cls.create(**kwargs)

        if cls._meta.strategy == enums.STUB_STRATEGY:
            return cls.stub(**kwargs)

        raise UnknownStrategy(f"Unknown '{cls.__name__}.Meta.strategy': {cls._meta.strategy}")


class AsyncSQLAlchemyModelFactory(Factory, metaclass=AsyncFactoryMetaClass):  # type: ignore[misc]
    _options_class = SQLAlchemyOptions

    class Meta:
        abstract = True

    @classmethod
    async def create(cls, **kwargs: typing.Any) -> T:  # noqa: ANN401
        return await cls._generate(enums.CREATE_STRATEGY, kwargs)

    @classmethod
    async def create_batch(cls, size: int, **kwargs: typing.Any) -> list[T]:  # noqa: ANN401
        return [await cls.create(**kwargs) for _ in range(size)]

    @classmethod
    async def _get_or_create(cls, model_class, session, args, kwargs):
        key_fields = {}
        for field in cls._meta.sqlalchemy_get_or_create:
            if field not in kwargs:
                raise errors.FactoryError(
                    "sqlalchemy_get_or_create - "
                    f"Unable to find initialization value for '{field}' in factory {cls.__name__}"
                )
            key_fields[field] = kwargs.pop(field)

        stmt = sa.select(model_class).filter_by(*args, **key_fields)
        result = await session.scalars(stmt)
        obj = result.one_or_none()

        if not obj:
            try:
                obj = await cls._save(model_class, session, args, {**key_fields, **kwargs})
            except sa.exc.IntegrityError as e:
                session.rollback()

                if cls._original_params is None:
                    raise e

                get_or_create_params = {
                    lookup: value
                    for lookup, value in cls._original_params.items()
                    if lookup in cls._meta.sqlalchemy_get_or_create
                }
                if get_or_create_params:
                    try:
                        stmt = sa.select(model_class).filter_by(**get_or_create_params)
                        result = await session.scalars(stmt)
                        obj = result.one()
                    except sa.exc.NoResultFound:
                        # Original params are not a valid lookup and triggered a create(),
                        # that resulted in an IntegrityError.
                        raise e
                else:
                    raise e

        return obj

    @classmethod
    async def _create(cls, model_class, *args, **kwargs):
        """Create an instance of the model, and save it to the database."""
        session_factory = cls._meta.sqlalchemy_session_factory
        if session_factory:
            cls._meta.sqlalchemy_session = session_factory()

        session = cls._meta.sqlalchemy_session

        if session is None:
            raise RuntimeError("No session provided.")
        if cls._meta.sqlalchemy_get_or_create:
            return await cls._get_or_create(model_class, session, args, kwargs)
        return await cls._save(model_class, session, args, kwargs)

    @classmethod
    async def _save(cls, model_class, session, args, kwargs):
        session_persistence = cls._meta.sqlalchemy_session_persistence

        obj = model_class(*args, **kwargs)
        session.add(obj)
        if session_persistence == SESSION_PERSISTENCE_FLUSH:
            await session.flush()
        elif session_persistence == SESSION_PERSISTENCE_COMMIT:
            await session.commit()
        return obj
