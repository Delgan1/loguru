import asyncio
import builtins
import contextlib
import datetime
import io
import logging
import multiprocessing
import os
import pathlib
import sys
import threading
import time
import traceback
import warnings
from typing import NamedTuple

import freezegun
import pytest

import loggerex

if sys.version_info < (3, 5, 3):

    def run(coro):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        res = loop.run_until_complete(coro)
        loop.close()
        asyncio.set_event_loop(None)
        return res

    asyncio.run = run
elif sys.version_info < (3, 7):

    def run(coro):
        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(coro)
        loop.close()
        asyncio.set_event_loop(None)
        return res

    asyncio.run = run

if sys.version_info < (3, 6):

    @pytest.fixture
    def tmp_path(tmp_path):
        return pathlib.Path(str(tmp_path))


try:
    from pytest_mypy_plugins.item import YamlTestItem
except ImportError:
    # The plugin is only available starting with Python 3.6.
    # Additionally, it has dependencies that are not compatible with Python versions in development.
    # In both cases, the Mypy tests will be skipped.
    pass
else:

    def _fix_positional_only_args(item: YamlTestItem):
        """Remove forward-slash marker from the expected output for Python 3.6."""
        for output in item.expected_output:
            output.message = output.message.replace(", /", "")
            # Also patch the "severity" attribute because there is a parsing bug in the plugin.
            output.severity = output.severity.replace(", /", "")

    def _add_mypy_config(item: YamlTestItem):
        """Add some extra options to the mypy configuration for Python 3.7+."""
        item.additional_mypy_config += "\n".join(
            [
                "show_error_codes = false",
                "force_uppercase_builtins = true",
                "force_union_syntax = true",
            ]
        )

    def pytest_collection_modifyitems(config, items):
        """Modify the tests to ensure they produce the same output regardless of Python version."""
        for item in items:
            if not isinstance(item, YamlTestItem):
                continue

            if sys.version_info >= (3, 7):
                _add_mypy_config(item)
            else:
                _fix_positional_only_args(item)


@contextlib.contextmanager
def new_event_loop_context():
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@contextlib.contextmanager
def set_event_loop_context(loop):
    asyncio.set_event_loop(loop)
    try:
        yield
    finally:
        asyncio.set_event_loop(None)


def parse(text, *, strip=False, strict=True):
    parser = loggerex._colorizer.AnsiParser()
    parser.feed(text)
    tokens = parser.done(strict=strict)

    if strip:
        return parser.strip(tokens)
    return parser.colorize(tokens, "")


def check_dir(dir, *, files=None, size=None):
    actual_files = set(dir.iterdir())
    seen = set()
    if size is not None:
        assert len(actual_files) == size
    if files is not None:
        assert len(actual_files) == len(files)
        for name, content in files:
            filepath = dir / name
            assert filepath in actual_files
            assert filepath not in seen
            if content is not None:
                assert filepath.read_text() == content
            seen.add(filepath)


class StubStream(io.StringIO):
    def fileno(self):
        return 1


class StreamIsattyTrue(StubStream):
    def isatty(self):
        return True


class StreamIsattyFalse(StubStream):
    def isatty(self):
        return False


class StreamIsattyException(StubStream):
    def isatty(self):
        raise RuntimeError


class StreamFilenoException(StreamIsattyTrue):
    def fileno(self):
        raise RuntimeError


@contextlib.contextmanager
def default_threading_excepthook():
    if not hasattr(threading, "excepthook"):
        yield
        return

    # Pytest added "PytestUnhandledThreadExceptionWarning", we need to
    # remove it temporarily for some tests checking exceptions in threads.

    def excepthook(args):
        print("Exception in thread:", file=sys.stderr, flush=True)
        traceback.print_exception(
            args.exc_type, args.exc_value, args.exc_traceback, file=sys.stderr
        )

    old_excepthook = threading.excepthook
    threading.excepthook = excepthook
    yield
    threading.excepthook = old_excepthook


@pytest.fixture(scope="session", autouse=True)
def check_env_variables():
    for var in os.environ:
        if var.startswith("LOGURU_"):
            warnings.warn(
                "A Loguru environment variable has been detected "
                "and may interfere with the tests: '%s'" % var,
                RuntimeWarning,
                stacklevel=1,
            )


@pytest.fixture(autouse=True)
def reset_logger():
    def reset():
        loggerex.logger.remove()
        loggerex.logger.__init__(
            loggerex._logger.Core(), None, 0, False, False, False, False, True, [], {}
        )
        loggerex._logger.context.set({})

    reset()
    yield
    reset()


@pytest.fixture
def writer():
    def w(message):
        w.written.append(message)

    w.written = []
    w.read = lambda: "".join(w.written)
    w.clear = lambda: w.written.clear()

    return w


@pytest.fixture
def sink_with_logger():
    class SinkWithLogger:
        def __init__(self, logger):
            self.logger = logger
            self.out = ""

        def write(self, message):
            self.logger.info(message)
            self.out += message

    return SinkWithLogger


@pytest.fixture
def freeze_time(monkeypatch):
    ctimes = {}
    freezegun_localtime = freezegun.api.fake_localtime
    builtins_open = builtins.open

    fakes = {
        "zone": "UTC",
        "offset": 0,
        "include_tm_zone": True,
        "tm_gmtoff_override": None,
    }

    def fake_localtime(t=None):
        fix_struct = os.name == "nt" and sys.version_info < (3, 6)

        struct_time_attributes = [
            ("tm_year", int),
            ("tm_mon", int),
            ("tm_mday", int),
            ("tm_hour", int),
            ("tm_min", int),
            ("tm_sec", int),
            ("tm_wday", int),
            ("tm_yday", int),
            ("tm_isdst", int),
            ("tm_zone", str),
            ("tm_gmtoff", int),
        ]

        if not fakes["include_tm_zone"]:
            struct_time_attributes = struct_time_attributes[:-2]
            struct_time = NamedTuple("struct_time", struct_time_attributes)._make
        elif fix_struct:
            struct_time = NamedTuple("struct_time", struct_time_attributes)._make
        else:
            struct_time = time.struct_time

        struct = freezegun_localtime(t)
        override = {"tm_zone": fakes["zone"], "tm_gmtoff": fakes["offset"]}
        attributes = []

        if fakes["tm_gmtoff_override"] is not None:
            override["tm_gmtoff"] = fakes["tm_gmtoff_override"]

        for attribute, _ in struct_time_attributes:
            if attribute in override:
                value = override[attribute]
            else:
                value = getattr(struct, attribute)
            attributes.append(value)

        return struct_time(attributes)

    def patched_open(filepath, *args, **kwargs):
        if not os.path.exists(filepath):
            tz = datetime.timezone(datetime.timedelta(seconds=fakes["offset"]), name=fakes["zone"])
            ctimes[filepath] = datetime.datetime.now().replace(tzinfo=tz).timestamp()
        return builtins_open(filepath, *args, **kwargs)

    @contextlib.contextmanager
    def freeze_time(date, timezone=("UTC", 0), *, include_tm_zone=True, tm_gmtoff_override=None):
        # Freezegun does not behave very well with UTC and timezones, see spulec/freezegun#348.
        # In particular, "now(tz=utc)" does not return the converted datetime.
        # For this reason, we re-implement date parsing here to properly handle aware date using
        # the optional "tz_offset" argument.
        if isinstance(date, str):
            for accepted_format in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"]:
                try:
                    date = datetime.datetime.strptime(date, accepted_format)
                    break
                except ValueError:
                    pass

        if not isinstance(date, datetime.datetime) or date.tzinfo is not None:
            raise ValueError("Unsupported date provided")

        zone, offset = timezone
        tz_offset = datetime.timedelta(seconds=offset)
        tzinfo = datetime.timezone(tz_offset, zone)
        date = date.replace(tzinfo=tzinfo)

        with monkeypatch.context() as context:
            context.setitem(fakes, "zone", zone)
            context.setitem(fakes, "offset", offset)
            context.setitem(fakes, "include_tm_zone", include_tm_zone)
            context.setitem(fakes, "tm_gmtoff_override", tm_gmtoff_override)

            context.setattr(loggerex._file_sink, "get_ctime", ctimes.__getitem__)
            context.setattr(loggerex._file_sink, "set_ctime", ctimes.__setitem__)
            context.setattr(builtins, "open", patched_open)

            # Freezegun does not permit to override timezone name.
            context.setattr(freezegun.api, "fake_localtime", fake_localtime)

            with freezegun.freeze_time(date, tz_offset=tz_offset) as frozen:
                yield frozen

    return freeze_time


@contextlib.contextmanager
def make_logging_logger(name, handler, fmt="%(message)s", level="DEBUG"):
    original_logging_level = logging.getLogger().getEffectiveLevel()
    logging_logger = logging.getLogger(name)
    logging_logger.setLevel(level)
    formatter = logging.Formatter(fmt)

    handler.setLevel(level)
    handler.setFormatter(formatter)
    logging_logger.addHandler(handler)

    try:
        yield logging_logger
    finally:
        logging_logger.setLevel(original_logging_level)
        logging_logger.removeHandler(handler)


def _simulate_f_globals_name_absent(monkeypatch):
    """Simulate execution in Dask environment, where "__name__" is not available in globals."""
    getframe_ = loggerex._get_frame.load_get_frame_function()

    def patched_getframe(*args, **kwargs):
        frame = getframe_(*args, **kwargs)
        frame.f_globals.pop("__name__", None)
        return frame

    with monkeypatch.context() as context:
        context.setattr(loggerex._logger, "get_frame", patched_getframe)
        yield


def _simulate_no_frame_available(monkeypatch):
    """Simulate execution in Cython, where there is no stack frame to retrieve."""

    def patched_getframe(*args, **kwargs):
        raise ValueError("Call stack is not deep enough (dummy)")

    with monkeypatch.context() as context:
        context.setattr(loggerex._logger, "get_frame", patched_getframe)
        yield


@pytest.fixture(params=[_simulate_f_globals_name_absent, _simulate_no_frame_available])
def incomplete_frame_context(request, monkeypatch):
    """Simulate different scenarios where the stack frame is incomplete or entirely absent."""
    yield from request.param(monkeypatch)


@pytest.fixture(autouse=True)
def reset_multiprocessing_start_method():
    multiprocessing.set_start_method(None, force=True)
    yield
    multiprocessing.set_start_method(None, force=True)
