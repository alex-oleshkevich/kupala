from kupala.choices import IntegerChoices, TextChoices


def test_text_choices_without_label() -> None:
    class Fruits(TextChoices):
        APPLE = "apple"
        PEAR = "pear"
        BANANA = "banana"

    assert Fruits.APPLE == Fruits("apple")
    assert Fruits.choices == (
        ("apple", "Apple"),
        ("pear", "Pear"),
        ("banana", "Banana"),
    )
    assert Fruits.labels == ("Apple", "Pear", "Banana")
    assert Fruits.values == ("apple", "pear", "banana")
    assert str(Fruits.APPLE) == "apple"


def test_text_choices_with_label() -> None:
    class Fruits(TextChoices):
        APPLE = ("apple", "Apple")
        PEAR = ("pear", "Pear")
        BANANA = ("banana", "Banana")

    assert Fruits.APPLE == "apple"
    assert Fruits.choices == (
        ("apple", "Apple"),
        ("pear", "Pear"),
        ("banana", "Banana"),
    )
    assert Fruits.labels == ("Apple", "Pear", "Banana")
    assert Fruits.values == ("apple", "pear", "banana")


def test_integer_choices_without_label() -> None:
    class Fruits(IntegerChoices):
        APPLE = 1, "Apple"
        PEAR = 2, "Pear"
        BANANA = 3, "Banana"

    assert Fruits.APPLE == Fruits(1)
    assert Fruits.choices == (
        (1, "Apple"),
        (2, "Pear"),
        (3, "Banana"),
    )
    assert Fruits.labels == ("Apple", "Pear", "Banana")
    assert Fruits.values == (1, 2, 3)


def test_integer_choices_with_label() -> None:
    class Fruits(IntegerChoices):
        APPLE = 1
        PEAR = 2
        BANANA = 3

    assert Fruits.APPLE == 1
    assert Fruits.choices == (
        (1, "Apple"),
        (2, "Pear"),
        (3, "Banana"),
    )
    assert Fruits.labels == ("Apple", "Pear", "Banana")
    assert Fruits.values == (1, 2, 3)
