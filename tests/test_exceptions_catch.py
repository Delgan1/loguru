import asyncio
import site
import sys
import sysconfig
import threading
import types

import pytest

from loggerex import logger


@pytest.mark.parametrize("diagnose", [False, True])
def test_caret_not_masked(writer, diagnose):
    logger.add(writer, backtrace=True, diagnose=diagnose, colorize=False, format="")

    @logger.catch
    def f(n):
        1 / n
        f(n - 1)

    f(30)

    assert sum(line.startswith("> ") for line in writer.read().splitlines()) == 1


@pytest.mark.parametrize("diagnose", [False, True])
def test_no_caret_if_no_backtrace(writer, diagnose):
    logger.add(writer, backtrace=False, diagnose=diagnose, colorize=False, format="")

    @logger.catch
    def f(n):
        1 / n
        f(n - 1)

    f(30)

    assert sum(line.startswith("> ") for line in writer.read().splitlines()) == 0


@pytest.mark.parametrize("encoding", ["ascii", "UTF8", None, "unknown-encoding", "", object()])
def test_sink_encoding(writer, encoding):
    class Writer:
        def __init__(self, encoding):
            self.encoding = encoding
            self.output = ""

        def write(self, message):
            self.output += message

    writer = Writer(encoding)
    logger.add(writer, backtrace=True, diagnose=True, colorize=False, format="", catch=False)

    def foo(a, b):
        a / b

    def bar(c):
        foo(c, 0)

    try:
        bar(4)
    except ZeroDivisionError:
        logger.exception("")

    assert writer.output.endswith("ZeroDivisionError: division by zero\n")


def test_file_sink_ascii_encoding(tmp_path):
    file = tmp_path / "test.log"
    logger.add(file, format="", encoding="ascii", errors="backslashreplace", catch=False)
    a = "天"

    try:
        "天" * a
    except Exception:
        logger.exception("")

    logger.remove()
    result = file.read_text("ascii")
    assert result.count('"\\u5929" * a') == 1
    assert result.count("-> '\\u5929'") == 1


def test_file_sink_utf8_encoding(tmp_path):
    file = tmp_path / "test.log"
    logger.add(file, format="", encoding="utf8", errors="strict", catch=False)
    a = "天"

    try:
        "天" * a
    except Exception:
        logger.exception("")

    logger.remove()
    result = file.read_text("utf8")
    assert result.count('"天" * a') == 1
    assert result.count("└ '天'") == 1


def test_has_sys_real_prefix(writer, monkeypatch):
    with monkeypatch.context() as context:
        context.setattr(sys, "real_prefix", "/foo/bar/baz", raising=False)
        logger.add(writer, backtrace=False, diagnose=True, colorize=False, format="")

        try:
            1 / 0  # noqa: B018
        except ZeroDivisionError:
            logger.exception("")

        assert writer.read().endswith("ZeroDivisionError: division by zero\n")


def test_no_sys_real_prefix(writer, monkeypatch):
    with monkeypatch.context() as context:
        context.delattr(sys, "real_prefix", raising=False)
        logger.add(writer, backtrace=False, diagnose=True, colorize=False, format="")

        try:
            1 / 0  # noqa: B018
        except ZeroDivisionError:
            logger.exception("")

        assert writer.read().endswith("ZeroDivisionError: division by zero\n")


def test_has_site_getsitepackages(writer, monkeypatch):
    with monkeypatch.context() as context:
        context.setattr(site, "getsitepackages", lambda: ["foo", "bar", "baz"], raising=False)
        logger.add(writer, backtrace=False, diagnose=True, colorize=False, format="")

        try:
            1 / 0  # noqa: B018
        except ZeroDivisionError:
            logger.exception("")

        assert writer.read().endswith("ZeroDivisionError: division by zero\n")


def test_no_site_getsitepackages(writer, monkeypatch):
    with monkeypatch.context() as context:
        context.delattr(site, "getsitepackages", raising=False)
        logger.add(writer, backtrace=False, diagnose=True, colorize=False, format="")

        try:
            1 / 0  # noqa: B018
        except ZeroDivisionError:
            logger.exception("")

        assert writer.read().endswith("ZeroDivisionError: division by zero\n")


def test_user_site_is_path(writer, monkeypatch):
    with monkeypatch.context() as context:
        context.setattr(site, "USER_SITE", "/foo/bar/baz")
        logger.add(writer, backtrace=False, diagnose=True, colorize=False, format="")

        try:
            1 / 0  # noqa: B018
        except ZeroDivisionError:
            logger.exception("")

        assert writer.read().endswith("ZeroDivisionError: division by zero\n")


def test_user_site_is_none(writer, monkeypatch):
    with monkeypatch.context() as context:
        context.setattr(site, "USER_SITE", None)
        logger.add(writer, backtrace=False, diagnose=True, colorize=False, format="")

        try:
            1 / 0  # noqa: B018
        except ZeroDivisionError:
            logger.exception("")

        assert writer.read().endswith("ZeroDivisionError: division by zero\n")


def test_sysconfig_get_path_return_path(writer, monkeypatch):
    with monkeypatch.context() as context:
        context.setattr(sysconfig, "get_path", lambda *a, **k: "/foo/bar/baz")
        logger.add(writer, backtrace=False, diagnose=True, colorize=False, format="")

        try:
            1 / 0  # noqa: B018
        except ZeroDivisionError:
            logger.exception("")

        assert writer.read().endswith("ZeroDivisionError: division by zero\n")


def test_sysconfig_get_path_return_none(writer, monkeypatch):
    with monkeypatch.context() as context:
        context.setattr(sysconfig, "get_path", lambda *a, **k: None)
        logger.add(writer, backtrace=False, diagnose=True, colorize=False, format="")

        try:
            1 / 0  # noqa: B018
        except ZeroDivisionError:
            logger.exception("")

        assert writer.read().endswith("ZeroDivisionError: division by zero\n")


def test_no_exception(writer):
    logger.add(writer, backtrace=False, diagnose=False, colorize=False, format="{message}")

    logger.exception("No Error.")

    assert writer.read() in (
        "No Error.\nNoneType\n",
        "No Error.\nNoneType: None\n",  # Old versions of Python 3.5
    )


def test_exception_is_none():
    err = object()

    def writer(msg):
        nonlocal err
        err = msg.record["exception"]

    logger.add(writer)

    logger.error("No exception")

    assert err is None


def test_exception_is_tuple():
    exception = None

    def writer(msg):
        nonlocal exception
        exception = msg.record["exception"]

    logger.add(writer, catch=False)

    try:
        1 / 0  # noqa: B018
    except ZeroDivisionError:
        logger.exception("Exception")
        reference = sys.exc_info()

    t_1, v_1, tb_1 = exception
    t_2, v_2, tb_2 = (x for x in exception)
    t_3, v_3, tb_3 = exception[0], exception[1], exception[2]
    t_4, v_4, tb_4 = exception.type, exception.value, exception.traceback

    assert isinstance(exception, tuple)
    assert len(exception) == 3
    assert exception == reference
    assert reference == exception
    assert not (exception != reference)
    assert not (reference != exception)
    assert all(t is ZeroDivisionError for t in (t_1, t_2, t_3, t_4))
    assert all(isinstance(v, ZeroDivisionError) for v in (v_1, v_2, v_3, v_4))
    assert all(isinstance(tb, types.TracebackType) for tb in (tb_1, tb_2, tb_3, tb_4))


@pytest.mark.parametrize(
    "exception", [ZeroDivisionError, ArithmeticError, (ValueError, ZeroDivisionError)]
)
def test_exception_not_raising(writer, exception):
    logger.add(writer)

    @logger.catch(exception)
    def a():
        1 / 0  # noqa: B018

    a()
    assert writer.read().endswith("ZeroDivisionError: division by zero\n")


@pytest.mark.parametrize("exception", [ValueError, ((SyntaxError, TypeError))])
def test_exception_raising(writer, exception):
    logger.add(writer)

    @logger.catch(exception=exception)
    def a():
        1 / 0  # noqa: B018

    with pytest.raises(ZeroDivisionError):
        a()

    assert writer.read() == ""


@pytest.mark.parametrize(
    "exclude", [ZeroDivisionError, ArithmeticError, (ValueError, ZeroDivisionError)]
)
@pytest.mark.parametrize("exception", [BaseException, ZeroDivisionError])
def test_exclude_exception_raising(writer, exclude, exception):
    logger.add(writer)

    @logger.catch(exception, exclude=exclude)
    def a():
        1 / 0  # noqa: B018

    with pytest.raises(ZeroDivisionError):
        a()

    assert writer.read() == ""


@pytest.mark.parametrize("exclude", [ValueError, ((SyntaxError, TypeError))])
@pytest.mark.parametrize("exception", [BaseException, ZeroDivisionError])
def test_exclude_exception_not_raising(writer, exclude, exception):
    logger.add(writer)

    @logger.catch(exception, exclude=exclude)
    def a():
        1 / 0  # noqa: B018

    a()
    assert writer.read().endswith("ZeroDivisionError: division by zero\n")


def test_reraise(writer):
    logger.add(writer)

    @logger.catch(reraise=True)
    def a():
        1 / 0  # noqa: B018

    with pytest.raises(ZeroDivisionError):
        a()

    assert writer.read().endswith("ZeroDivisionError: division by zero\n")


def test_onerror(writer):
    is_error_valid = False
    logger.add(writer, format="{message}")

    def onerror(error):
        nonlocal is_error_valid
        logger.info("Called after logged message")
        _, exception, _ = sys.exc_info()
        is_error_valid = (error == exception) and isinstance(error, ZeroDivisionError)

    @logger.catch(onerror=onerror)
    def a():
        1 / 0  # noqa: B018

    a()

    assert is_error_valid
    assert writer.read().endswith(
        "ZeroDivisionError: division by zero\n" "Called after logged message\n"
    )


def test_onerror_with_reraise(writer):
    called = False
    logger.add(writer, format="{message}")

    def onerror(_):
        nonlocal called
        called = True

    with pytest.raises(ZeroDivisionError):
        with logger.catch(onerror=onerror, reraise=True):
            1 / 0  # noqa: B018

    assert called


def test_decorate_function(writer):
    logger.add(writer, format="{message}", diagnose=False, backtrace=False, colorize=False)

    @logger.catch
    def a(x):
        return 100 / x

    assert a(50) == 2
    assert writer.read() == ""


def test_decorate_coroutine(writer):
    logger.add(writer, format="{message}", diagnose=False, backtrace=False, colorize=False)

    @logger.catch
    async def foo(a, b):
        return a + b

    result = asyncio.run(foo(100, 5))

    assert result == 105
    assert writer.read() == ""


def test_decorate_generator(writer):
    @logger.catch
    def foo(x, y, z):
        yield x
        yield y
        return z

    f = foo(1, 2, 3)
    assert next(f) == 1
    assert next(f) == 2

    with pytest.raises(StopIteration, match=r"3"):
        next(f)


def test_decorate_generator_with_error():
    @logger.catch
    def foo():
        yield 0
        yield 1
        raise ValueError

    assert list(foo()) == [0, 1]


def test_default_with_function():
    @logger.catch(default=42)
    def foo():
        1 / 0  # noqa: B018

    assert foo() == 42


def test_default_with_generator():
    @logger.catch(default=42)
    def foo():
        yield 1 / 0

    with pytest.raises(StopIteration, match=r"42"):
        next(foo())


def test_default_with_coroutine():
    @logger.catch(default=42)
    async def foo():
        return 1 / 0

    assert asyncio.run(foo()) == 42


def test_async_context_manager():
    async def coro():
        async with logger.catch():
            return 1 / 0
        return 1

    assert asyncio.run(coro()) == 1


def test_error_when_decorating_class_without_parentheses():
    with pytest.raises(TypeError):

        @logger.catch
        class Foo:
            pass


def test_error_when_decorating_class_with_parentheses():
    with pytest.raises(TypeError):

        @logger.catch()
        class Foo:
            pass


def test_unprintable_but_decorated_repr(writer):

    class Foo:
        @logger.catch(reraise=True)
        def __repr__(self):
            raise ValueError("Something went wrong")

    logger.add(writer, backtrace=True, diagnose=True, colorize=False, format="", catch=False)

    foo = Foo()

    with pytest.raises(ValueError, match="^Something went wrong$"):
        repr(foo)

    assert writer.read().endswith("ValueError: Something went wrong\n")


def test_unprintable_but_decorated_repr_without_reraise(writer):
    class Foo:
        @logger.catch(reraise=False, default="?")
        def __repr__(self):
            raise ValueError("Something went wrong")

    logger.add(writer, backtrace=True, diagnose=True, colorize=False, format="", catch=False)

    foo = Foo()

    repr(foo)

    assert writer.read().endswith("ValueError: Something went wrong\n")


def test_unprintable_but_decorated_multiple_sinks(capsys):
    class Foo:
        @logger.catch(reraise=True)
        def __repr__(self):
            raise ValueError("Something went wrong")

    logger.add(sys.stderr, backtrace=True, diagnose=True, colorize=False, format="", catch=False)
    logger.add(sys.stdout, backtrace=True, diagnose=True, colorize=False, format="", catch=False)

    foo = Foo()

    with pytest.raises(ValueError, match="^Something went wrong$"):
        repr(foo)

    out, err = capsys.readouterr()
    assert out.endswith("ValueError: Something went wrong\n")
    assert err.endswith("ValueError: Something went wrong\n")


def test_unprintable_but_decorated_repr_with_enqueue(writer):
    class Foo:
        @logger.catch(reraise=True)
        def __repr__(self):
            raise ValueError("Something went wrong")

    logger.add(
        writer, backtrace=True, diagnose=True, colorize=False, format="", catch=False, enqueue=True
    )

    foo = Foo()

    with pytest.raises(ValueError, match="^Something went wrong$"):
        repr(foo)

    logger.complete()

    assert writer.read().endswith("ValueError: Something went wrong\n")


def test_unprintable_but_decorated_repr_twice(writer):
    class Foo:
        @logger.catch(reraise=True)
        @logger.catch(reraise=True)
        def __repr__(self):
            raise ValueError("Something went wrong")

    logger.add(writer, backtrace=True, diagnose=True, colorize=False, format="", catch=False)

    foo = Foo()

    with pytest.raises(ValueError, match="^Something went wrong$"):
        repr(foo)

    assert writer.read().endswith("ValueError: Something went wrong\n")


def test_unprintable_with_catch_context_manager(writer):
    class Foo:
        def __repr__(self):
            with logger.catch(reraise=True):
                raise ValueError("Something went wrong")

    logger.add(writer, backtrace=True, diagnose=True, colorize=False, format="", catch=False)

    foo = Foo()

    with pytest.raises(ValueError, match="^Something went wrong$"):
        repr(foo)

    assert writer.read().endswith("ValueError: Something went wrong\n")


def test_unprintable_with_catch_context_manager_reused(writer):
    def sink(_):
        raise ValueError("Sink error")

    logger.remove()
    logger.add(sink, catch=False)

    catcher = logger.catch(reraise=False)

    class Foo:
        def __repr__(self):
            with catcher:
                raise ValueError("Something went wrong")

    foo = Foo()

    with pytest.raises(ValueError, match="^Sink error$"):
        repr(foo)

    logger.remove()
    logger.add(writer)

    with catcher:
        raise ValueError("Error")

    assert writer.read().endswith("ValueError: Error\n")


def test_unprintable_but_decorated_repr_multiple_threads(writer):
    wait_for_repr_block = threading.Event()
    wait_for_worker_finish = threading.Event()

    recursive = False

    class Foo:
        @logger.catch(reraise=True)
        def __repr__(self):
            nonlocal recursive
            if not recursive:
                recursive = True
            else:
                wait_for_repr_block.set()
                wait_for_worker_finish.wait()
            raise ValueError("Something went wrong")

    def worker():
        wait_for_repr_block.wait()
        with logger.catch(reraise=False):
            raise ValueError("Worker error")
        wait_for_worker_finish.set()

    logger.add(writer, backtrace=True, diagnose=True, colorize=False, format="", catch=False)

    thread = threading.Thread(target=worker)
    thread.start()

    foo = Foo()

    with pytest.raises(ValueError, match="^Something went wrong$"):
        repr(foo)

    thread.join()

    assert "ValueError: Worker error\n" in writer.read()
    assert writer.read().endswith("ValueError: Something went wrong\n")
