import re

import pytest

from loggerex import logger


@pytest.mark.parametrize(
    "filter",
    [
        None,
        "",
        "tests",
        "tests.test_add_option_filter",
        (lambda r: True),
        (lambda r: r["level"].name == "DEBUG"),
        {},
        {"": "DEBUG"},
        {"tests": True},
        {"tests.test_add_option_filter": 10},
        {"": "WARNING", "tests": 0},
        {"tests.test_add_option_filter": 5, "tests": False},
        {"tests.test_add_option_filter.foobar": False},
        {"tests.": False},
        {"tests.test_add_option_filter.": False},
    ],
)
def test_filtered_in(filter, writer):
    logger.add(writer, filter=filter, format="{message}")
    logger.debug("Test Filter")
    assert writer.read() == "Test Filter\n"


@pytest.mark.parametrize(
    "filter",
    [
        "test",
        "testss",
        "tests.",
        "tests.test_add_option_filter.",
        ".",
        (lambda r: False),
        (lambda r: r["level"].no != 10),
        {"": False},
        {"": True, "tests": 50},
        {"tests.test_add_option_filter": False},
        {"tests": "WARNING"},
        {"tests": 5, "tests.test_add_option_filter": 40},
        {"": 100, "tests.test_add_option_filter.foobar": True},
    ],
)
def test_filtered_out(filter, writer):
    logger.add(writer, filter=filter, format="{message}")
    logger.debug("Test Filter")
    assert writer.read() == ""


@pytest.mark.parametrize(
    "filter",
    [
        None,
        lambda _: True,
        {},
        {None: 0},
        {"": False},
        {"tests": False, None: True},
        {"unrelated": 100},
        {None: "INFO", "": "WARNING"},
    ],
)
def test_filtered_in_incomplete_frame_context(writer, filter, incomplete_frame_context):
    logger.add(writer, filter=filter, format="{message}", catch=False)
    logger.info("It's ok")
    assert writer.read() == "It's ok\n"


@pytest.mark.parametrize(
    "filter",
    [
        "tests",
        "",
        lambda _: False,
        {None: False},
        {"": 0, None: "WARNING"},
        {None: 100, "tests": True},
    ],
)
def test_filtered_out_incomplete_frame_context(writer, filter, incomplete_frame_context):
    logger.add(writer, filter=filter, format="{message}", catch=False)
    logger.info("It's not ok")
    assert writer.read() == ""


@pytest.mark.parametrize("filter", [-1, 3.4, object()])
def test_invalid_filter(writer, filter):
    with pytest.raises(TypeError):
        logger.add(writer, filter=filter)


@pytest.mark.parametrize("filter", [{"foo": None}, {"foo": 2.5}, {"a": "DEBUG", "b": object()}])
def test_invalid_filter_dict_level_types(writer, filter):
    with pytest.raises(TypeError):
        logger.add(writer, filter=filter)


@pytest.mark.parametrize("filter", [{1: "DEBUG"}, {object(): 10}])
def test_invalid_filter_dict_module_types(writer, filter):
    with pytest.raises(TypeError):
        logger.add(writer, filter=filter)


@pytest.mark.parametrize("filter", [{"foo": "UNKNOWN_LEVEL"}, {"tests.test_add_option_filter": ""}])
def test_invalid_filter_dict_values_unknown_level(writer, filter):
    with pytest.raises(
        ValueError,
        match=(
            "The filter dict contains a module '[^']*' associated to "
            "a level name which does not exist: '[^']*'"
        ),
    ):
        logger.add(writer, filter=filter)


def test_invalid_filter_dict_values_wrong_integer_value(writer):
    with pytest.raises(
        ValueError,
        match=(
            "The filter dict contains a module '[^']*' associated to an invalid level, "
            "it should be a positive integer, not: '[^']*'"
        ),
    ):
        logger.add(writer, filter={"tests": -1})


def test_filter_dict_with_custom_level(writer):
    logger.level("MY_LEVEL", 6, color="", icon="")
    logger.add(writer, level=0, filter={"tests": "MY_LEVEL"}, format="{message}")
    logger.log(3, "No")
    logger.log(9, "Yes")
    assert writer.read() == "Yes\n"


def test_invalid_filter_builtin(writer):
    with pytest.raises(
        ValueError,
        match=re.escape(
            "The built-in 'filter()' function cannot be used as a 'filter' parameter, this is "
            "most likely a mistake (please double-check the arguments passed to 'logger.add()'"
        ),
    ):
        logger.add(writer, filter=filter)
