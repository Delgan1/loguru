import sys

from loggerex import logger


def test(diagnose, backtrace):
    logger.remove()
    logger.add(sys.stderr, format="", diagnose=diagnose, backtrace=backtrace, colorize=True)

    try:
        1 / 0
    except ZeroDivisionError:
        type_, value, _ = sys.exc_info()
        logger.opt(exception=(type_, value, None)).error("")


test(False, False)
test(True, False)
test(False, True)
test(True, True)
