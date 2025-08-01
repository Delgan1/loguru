import os

import pytest

from loggerex import logger

from .conftest import StreamIsattyException, StreamIsattyFalse, StreamIsattyTrue, parse


@pytest.mark.parametrize(
    ("format", "message", "expected"),
    [
        ("<red>{message}</red>", "Foo", parse("<red>Foo</red>\n")),
        (lambda _: "<red>{message}</red>", "Bar", parse("<red>Bar</red>")),
        ("{message}", "<red>Baz</red>", "<red>Baz</red>\n"),
        ("{{<red>{message:}</red>}}", "A", parse("{<red>A</red>}\n")),
    ],
)
def test_colorized_format(format, message, expected, writer):
    logger.add(writer, format=format, colorize=True)
    logger.debug(message)
    assert writer.read() == expected


@pytest.mark.parametrize(
    ("format", "message", "expected"),
    [
        ("<red>{message}</red>", "Foo", "Foo\n"),
        (lambda _: "<red>{message}</red>", "Bar", "Bar"),
        ("{message}", "<red>Baz</red>", "<red>Baz</red>\n"),
        ("{{<red>{message:}</red>}}", "A", "{A}\n"),
    ],
)
def test_decolorized_format(format, message, expected, writer):
    logger.add(writer, format=format, colorize=False)
    logger.debug(message)
    assert writer.read() == expected


@pytest.mark.parametrize(
    "stream", [StreamIsattyTrue(), StreamIsattyFalse(), StreamIsattyException()]
)
def test_colorize_stream(stream):
    logger.add(stream, format="<blue>{message}</blue>", colorize=True)
    logger.debug("Message")
    assert stream.getvalue() == parse("<blue>Message</blue>\n")


@pytest.mark.parametrize(
    "stream", [StreamIsattyTrue(), StreamIsattyFalse(), StreamIsattyException()]
)
def test_decolorize_stream(stream):
    stream = StreamIsattyFalse()
    logger.add(stream, format="<blue>{message}</blue>", colorize=False)
    logger.debug("Message")
    assert stream.getvalue() == "Message\n"


def test_automatic_detection_when_stream_is_a_tty():
    stream = StreamIsattyTrue()
    logger.add(stream, format="<blue>{message}</blue>", colorize=None)
    logger.debug("Message")
    assert stream.getvalue() == parse("<blue>Message</blue>\n")


def test_automatic_detection_when_stream_is_not_a_tty():
    stream = StreamIsattyFalse()
    logger.add(stream, format="<blue>{message}</blue>", colorize=None)
    logger.debug("Message")
    assert stream.getvalue() == "Message\n"


def test_automatic_detection_when_stream_has_no_isatty():
    stream = StreamIsattyException()
    logger.add(stream, format="<blue>{message}</blue>", colorize=None)
    logger.debug("Message")
    assert stream.getvalue() == "Message\n"


def test_override_no_color(monkeypatch):
    stream = StreamIsattyTrue()
    with monkeypatch.context() as context:
        context.setitem(os.environ, "NO_COLOR", "1")
        logger.add(stream, format="<blue>{message}</blue>", colorize=True)
        logger.debug("Message", colorize=False)
        assert stream.getvalue() == parse("<blue>Message</blue>\n")


def test_override_force_color(monkeypatch):
    stream = StreamIsattyFalse()
    with monkeypatch.context() as context:
        context.setitem(os.environ, "FORCE_COLOR", "1")
        logger.add(stream, format="<blue>{message}</blue>", colorize=False)
        logger.debug("Message", colorize=False)
        assert stream.getvalue() == "Message\n"
