import typing

import msgspec
import pydantic
import pytest
from starlette.datastructures import QueryParams

from kupala.binders import DEFAULT_MODEL_BINDERS, MsgspecBinder, PydanticBinder, holds_a_sequence
from kupala.errors import ValidationError

type Tags = list[str]


class Filters(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    page: int = 1
    tags: list[str] = pydantic.Field(default_factory=list)


class AliasedAnnotation(pydantic.BaseModel):
    tags: Tags = pydantic.Field(default_factory=list)


class AliasedStructAnnotation(msgspec.Struct):
    tags: Tags = []


class AliasedFilters(pydantic.BaseModel):
    terms: list[str] = pydantic.Field(default_factory=list, alias="tag")


class Credentials(pydantic.BaseModel):
    password: int


class StructFilters(msgspec.Struct):
    page: int = 1
    tags: list[str] = []


class RenamedFilters(msgspec.Struct, rename={"terms": "tag"}):
    terms: list[str] = []


class TestHoldsASequence:
    @pytest.mark.parametrize(
        "annotation", [list[str], set[int], frozenset[str], tuple[int, ...], list, list[str] | None]
    )
    def test_accepts_sequences(self, annotation: typing.Any) -> None:
        assert holds_a_sequence(annotation)

    @pytest.mark.parametrize("annotation", [Tags, Tags | None])
    def test_looks_through_a_type_alias(self, annotation: typing.Any) -> None:
        # both libraries report a `type` alias verbatim, so an unresolved one would collapse a repeated key
        assert holds_a_sequence(annotation)

    @pytest.mark.parametrize("annotation", [str, bytes, bytearray, int, dict[str, str], int | None])
    def test_rejects_everything_else(self, annotation: typing.Any) -> None:
        # a string is a Sequence, so accepting one would turn a single value into a list of characters
        assert not holds_a_sequence(annotation)


class TestPydanticBinder:
    def test_claims_a_model(self) -> None:
        assert PydanticBinder().supports(Filters)

    @pytest.mark.parametrize("type_", [StructFilters, int, dict])
    def test_claims_nothing_else(self, type_: type) -> None:
        assert not PydanticBinder().supports(type_)

    def test_builds_a_model(self) -> None:
        build = PydanticBinder().compile(Filters, coerce=True)

        assert build({"page": "2", "tags": ["a", "b"]}) == Filters(page=2, tags=["a", "b"])

    def test_a_repeated_key_fills_a_sequence_field(self) -> None:
        build = PydanticBinder().compile(Filters, coerce=True)

        assert build(QueryParams("page=2&tags=a&tags=b")) == Filters(page=2, tags=["a", "b"])

    def test_a_repeated_key_arrives_under_the_field_alias(self) -> None:
        # the request carries the alias, so that is the key a repeated value arrives under
        build = PydanticBinder().compile(AliasedFilters, coerce=True)

        assert build(QueryParams("tag=a&tag=b")).terms == ["a", "b"]

    def test_looks_through_a_type_alias_on_the_field(self) -> None:
        build = PydanticBinder().compile(AliasedAnnotation, coerce=True)

        assert build(QueryParams("tags=a&tags=b")).tags == ["a", "b"]

    def test_an_unrecognised_key_is_carried_over(self) -> None:
        # otherwise a model configured with extra="forbid" would never see one to reject
        build = PydanticBinder().compile(Filters, coerce=True)

        with pytest.raises(ValidationError) as info:
            build(QueryParams("nonsense=1"))

        assert set(info.value.errors) == {"nonsense"}

    def test_reports_one_error_per_field(self) -> None:
        build = PydanticBinder().compile(Filters, coerce=True)

        with pytest.raises(ValidationError) as info:
            build({"page": "many", "tags": "not-a-list"})

        assert set(info.value.errors) == {"page", "tags"}
        assert len(info.value.errors["page"]) == 1

    def test_keys_a_nested_error_by_its_path(self) -> None:
        build = PydanticBinder().compile(Filters, coerce=True)

        with pytest.raises(ValidationError) as info:
            build({"tags": ["fine", {}]})

        assert set(info.value.errors) == {"tags.1"}

    def test_never_echoes_the_submitted_value(self) -> None:
        build = PydanticBinder().compile(Credentials, coerce=True)

        with pytest.raises(ValidationError) as info:
            build({"password": "hunter2"})

        assert "hunter2" not in str(info.value.errors)

    def test_describes_the_model(self) -> None:
        schema = PydanticBinder().schema(Filters)

        assert schema["type"] == "object"
        assert schema["properties"]["page"]["type"] == "integer"
        assert schema["properties"]["tags"]["type"] == "array"

    def test_describes_a_field_under_its_alias(self) -> None:
        schema = PydanticBinder().schema(AliasedFilters)

        assert "tag" in schema["properties"]
        assert "terms" not in schema["properties"]


class TestMsgspecBinder:
    def test_claims_a_struct(self) -> None:
        assert MsgspecBinder().supports(StructFilters)

    @pytest.mark.parametrize("type_", [Filters, int, dict])
    def test_claims_nothing_else(self, type_: type) -> None:
        assert not MsgspecBinder().supports(type_)

    def test_a_repeated_key_fills_a_sequence_field(self) -> None:
        build = MsgspecBinder().compile(StructFilters, coerce=True)

        assert build(QueryParams("page=2&tags=a&tags=b")) == StructFilters(page=2, tags=["a", "b"])

    def test_a_repeated_key_arrives_under_the_renamed_field(self) -> None:
        build = MsgspecBinder().compile(RenamedFilters, coerce=True)

        assert build(QueryParams("tag=a&tag=b")).terms == ["a", "b"]

    def test_looks_through_a_type_alias_on_the_field(self) -> None:
        build = MsgspecBinder().compile(AliasedStructAnnotation, coerce=True)

        assert build(QueryParams("tags=a&tags=b")).tags == ["a", "b"]

    def test_converts_strings_when_asked_to(self) -> None:
        # query and form values are always strings, so a model bound from one needs the lax path
        build = MsgspecBinder().compile(StructFilters, coerce=True)

        assert build({"page": "2"}) == StructFilters(page=2)

    def test_keeps_json_types_intact(self) -> None:
        build = MsgspecBinder().compile(StructFilters, coerce=False)

        with pytest.raises(ValidationError):
            # a JSON document already carries types, so a string where an int belongs is the client's error
            build({"page": "2"})

    def test_reports_every_error_under_one_key(self) -> None:
        # msgspec raises a single message naming the expected type and its location, with no field to key on
        build = MsgspecBinder().compile(StructFilters, coerce=True)

        with pytest.raises(ValidationError) as info:
            build({"page": "many"})

        assert set(info.value.errors) == {""}

    def test_describes_the_struct(self) -> None:
        schema = MsgspecBinder().schema(StructFilters)

        described = schema["$defs"]["StructFilters"]
        assert described["type"] == "object"
        assert described["properties"]["page"]["type"] == "integer"
        assert described["properties"]["tags"]["type"] == "array"

    def test_describes_a_field_under_its_encoded_name(self) -> None:
        schema = MsgspecBinder().schema(RenamedFilters)

        described = schema["$defs"]["RenamedFilters"]
        assert "tag" in described["properties"]
        assert "terms" not in described["properties"]


def test_default_binders_cover_both_libraries() -> None:
    assert [type(binder) for binder in DEFAULT_MODEL_BINDERS] == [PydanticBinder, MsgspecBinder]
