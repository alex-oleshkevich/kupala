import pytest

from kupala.types import MultiDict, MutableMultiDict


class TestMultiDictInit:
    def test_empty(self) -> None:
        md = MultiDict()
        assert len(md) == 0
        assert list(md) == []

    def test_from_pairs(self) -> None:
        md = MultiDict([("a", "1"), ("b", "2")])
        assert md["a"] == "1"
        assert md["b"] == "2"

    def test_from_iterator(self) -> None:
        md = MultiDict(iter([("a", "1"), ("b", "2")]))
        assert md["a"] == "1"

    def test_from_duplicated_keys(self) -> None:
        md = MultiDict([("a", "1"), ("a", "2")])
        assert md["a"] == "2"
        assert md.getlist("a") == ["1", "2"]


class TestMultiDictGetItem:
    def test_returns_last_value(self) -> None:
        md = MultiDict([("a", "1"), ("a", "2"), ("a", "3")])
        assert md["a"] == "3"

    def test_missing_raises_keyerror(self) -> None:
        md = MultiDict()
        with pytest.raises(KeyError):
            md["missing"]

    def test_case_sensitive(self) -> None:
        md = MultiDict([("Foo", "1")])
        assert md["Foo"] == "1"
        with pytest.raises(KeyError):
            md["foo"]


class TestMultiDictGet:
    def test_present(self) -> None:
        md = MultiDict([("a", "1")])
        assert md.get("a") == "1"

    def test_returns_last_value(self) -> None:
        md = MultiDict([("a", "1"), ("a", "2")])
        assert md.get("a") == "2"

    def test_missing_returns_none(self) -> None:
        md = MultiDict()
        assert md.get("a") is None

    def test_missing_with_default(self) -> None:
        md = MultiDict()
        assert md.get("a", "d") == "d"


class TestMultiDictGetList:
    def test_single_value(self) -> None:
        md = MultiDict([("a", "1")])
        assert md.getlist("a") == ["1"]

    def test_multiple_values_preserved_in_order(self) -> None:
        md = MultiDict([("a", "1"), ("b", "2"), ("a", "3")])
        assert md.getlist("a") == ["1", "3"]

    def test_missing_returns_empty(self) -> None:
        md = MultiDict([("a", "1")])
        assert md.getlist("missing") == []


class TestMultiDictContains:
    def test_present(self) -> None:
        md = MultiDict([("a", "1")])
        assert "a" in md

    def test_absent(self) -> None:
        md = MultiDict([("a", "1")])
        assert "b" not in md

    def test_duplicate_key(self) -> None:
        md = MultiDict([("a", "1"), ("a", "2")])
        assert "a" in md


class TestMultiDictIteration:
    def test_yields_unique_keys(self) -> None:
        md = MultiDict([("a", "1"), ("b", "2"), ("a", "3")])
        assert list(md) == ["a", "b"]

    def test_preserves_insertion_order(self) -> None:
        md = MultiDict([("c", "1"), ("a", "2"), ("b", "3")])
        assert list(md) == ["c", "a", "b"]

    def test_len_counts_unique_keys(self) -> None:
        md = MultiDict([("a", "1"), ("a", "2"), ("b", "3")])
        assert len(md) == 2

    def test_keys(self) -> None:
        md = MultiDict([("a", "1"), ("b", "2"), ("a", "3")])
        assert list(md.keys()) == ["a", "b"]

    def test_values_returns_last_per_key(self) -> None:
        md = MultiDict([("a", "1"), ("a", "2"), ("b", "3")])
        assert list(md.values()) == ["2", "3"]

    def test_items_returns_last_per_key(self) -> None:
        md = MultiDict([("a", "1"), ("a", "2"), ("b", "3")])
        assert list(md.items()) == [("a", "2"), ("b", "3")]


class TestMultiDictMultiItems:
    def test_preserves_duplicates(self) -> None:
        md = MultiDict([("a", "1"), ("a", "2")])
        assert md.multi_items() == [("a", "1"), ("a", "2")]

    def test_preserves_interleaving(self) -> None:
        md = MultiDict([("a", "1"), ("b", "2"), ("a", "3")])
        assert md.multi_items() == [("a", "1"), ("b", "2"), ("a", "3")]

    def test_empty(self) -> None:
        assert MultiDict().multi_items() == []

    def test_returns_copy(self) -> None:
        md = MultiDict([("a", "1")])
        items = md.multi_items()
        items.append(("b", "2"))
        assert md.multi_items() == [("a", "1")]


class TestMultiDictEquality:
    def test_equal_when_items_match(self) -> None:
        a = MultiDict([("a", "1"), ("b", "2")])
        b = MultiDict([("a", "1"), ("b", "2")])
        assert a == b

    def test_equal_when_order_differs(self) -> None:
        a = MultiDict([("a", "1"), ("b", "2")])
        b = MultiDict([("b", "2"), ("a", "1")])
        assert a == b

    def test_unequal_when_values_differ(self) -> None:
        a = MultiDict([("a", "1")])
        b = MultiDict([("a", "2")])
        assert a != b

    def test_unequal_when_duplicate_count_differs(self) -> None:
        a = MultiDict([("a", "1"), ("a", "2")])
        b = MultiDict([("a", "1")])
        assert a != b

    def test_not_equal_to_dict(self) -> None:
        md = MultiDict([("a", "1")])
        assert md != {"a": "1"}


class TestMultiDictRepr:
    def test_repr_shows_pairs(self) -> None:
        md = MultiDict([("a", "1"), ("b", "2")])
        assert repr(md) == "MultiDict([('a', '1'), ('b', '2')])"

    def test_repr_of_empty(self) -> None:
        assert repr(MultiDict()) == "MultiDict([])"


class TestMultiDictFromBytes:
    def test_decodes_latin1(self) -> None:
        md = MultiDict.from_bytes([(b"a", b"1"), (b"b", b"2")])
        assert md["a"] == "1"
        assert md["b"] == "2"

    def test_preserves_duplicates(self) -> None:
        md = MultiDict.from_bytes([(b"X", b"1"), (b"X", b"2")])
        assert md.getlist("X") == ["1", "2"]

    def test_empty(self) -> None:
        md = MultiDict.from_bytes([])
        assert len(md) == 0

    def test_high_byte_value(self) -> None:
        md = MultiDict.from_bytes([(b"key", b"\xe9")])
        assert md["key"] == "\xe9"


class TestMultiDictImmutability:
    def test_no_setitem(self) -> None:
        md = MultiDict([("a", "1")])
        with pytest.raises(TypeError):
            md["a"] = "2"  # type: ignore[index]

    def test_no_delitem(self) -> None:
        md = MultiDict([("a", "1")])
        with pytest.raises(TypeError):
            del md["a"]  # type: ignore[attr-defined]

    def test_no_append(self) -> None:
        md = MultiDict([("a", "1")])
        assert not hasattr(md, "append")

    def test_mutable_is_subclass(self) -> None:
        assert issubclass(MutableMultiDict, MultiDict)

    def test_immutable_equals_mutable_with_same_items(self) -> None:
        a = MultiDict([("a", "1")])
        b = MutableMultiDict([("a", "1")])
        assert a == b


class TestMutableMultiDict:
    def test_setitem_new_key(self) -> None:
        md = MutableMultiDict()
        md["a"] = "1"
        assert md["a"] == "1"
        assert md.multi_items() == [("a", "1")]

    def test_setitem_replaces_existing(self) -> None:
        md = MutableMultiDict([("a", "1"), ("a", "2")])
        md["a"] = "3"
        assert md["a"] == "3"
        assert md.getlist("a") == ["3"]

    def test_delitem(self) -> None:
        md = MutableMultiDict([("a", "1"), ("b", "2"), ("a", "3")])
        del md["a"]
        assert "a" not in md
        assert md.multi_items() == [("b", "2")]

    def test_delitem_missing_raises(self) -> None:
        md = MutableMultiDict()
        with pytest.raises(KeyError):
            del md["missing"]

    def test_append_new_key(self) -> None:
        md = MutableMultiDict()
        md.append("a", "1")
        assert md["a"] == "1"

    def test_append_preserves_existing(self) -> None:
        md = MutableMultiDict([("a", "1")])
        md.append("a", "2")
        assert md.getlist("a") == ["1", "2"]
        assert md["a"] == "2"

    def test_setlist_replaces_all_for_key(self) -> None:
        md = MutableMultiDict([("a", "1"), ("a", "2"), ("b", "3")])
        md.setlist("a", ["x", "y"])
        assert md.getlist("a") == ["x", "y"]
        assert md.getlist("b") == ["3"]

    def test_setlist_empty_removes_key(self) -> None:
        md = MutableMultiDict([("a", "1")])
        md.setlist("a", [])
        assert "a" not in md

    def test_pop_returns_last_and_removes_all(self) -> None:
        md = MutableMultiDict([("a", "1"), ("a", "2"), ("b", "3")])
        result = md.pop("a")
        assert result == "2"
        assert "a" not in md
        assert md.getlist("a") == []

    def test_pop_missing_returns_default(self) -> None:
        md = MutableMultiDict()
        assert md.pop("missing", "d") == "d"

    def test_poplist_returns_all_values(self) -> None:
        md = MutableMultiDict([("a", "1"), ("a", "2"), ("b", "3")])
        result = md.poplist("a")
        assert result == ["1", "2"]
        assert "a" not in md

    def test_popitem_removes_last_inserted(self) -> None:
        md = MutableMultiDict([("a", "1"), ("b", "2")])
        key, value = md.popitem()
        assert (key, value) == ("b", "2")
        assert "b" not in md

    def test_popitem_empty_raises(self) -> None:
        md = MutableMultiDict()
        with pytest.raises(KeyError):
            md.popitem()

    def test_clear(self) -> None:
        md = MutableMultiDict([("a", "1"), ("b", "2")])
        md.clear()
        assert len(md) == 0
        assert md.multi_items() == []

    def test_setdefault_missing_inserts(self) -> None:
        md = MutableMultiDict()
        result = md.setdefault("a", "1")
        assert result == "1"
        assert md["a"] == "1"

    def test_setdefault_existing_keeps_value(self) -> None:
        md = MutableMultiDict([("a", "1")])
        result = md.setdefault("a", "999")
        assert result == "1"
        assert md["a"] == "1"

    def test_update_from_mapping(self) -> None:
        md = MutableMultiDict([("a", "1"), ("b", "2")])
        md.update({"a": "x", "c": "3"})
        assert md["a"] == "x"
        assert md["c"] == "3"
        assert md["b"] == "2"

    def test_update_from_multidict(self) -> None:
        md = MutableMultiDict([("a", "1")])
        md.update(MutableMultiDict([("a", "2"), ("a", "3")]))
        assert md.getlist("a") == ["2", "3"]

    def test_update_from_iterable(self) -> None:
        md = MutableMultiDict([("a", "1")])
        md.update([("a", "2"), ("b", "3")])
        assert md["a"] == "2"
        assert md["b"] == "3"
