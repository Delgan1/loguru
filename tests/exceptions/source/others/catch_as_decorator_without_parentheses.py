import sys

from loggerex import logger

logger.remove()
logger.add(sys.stderr, format="", diagnose=False, backtrace=False, colorize=False)


@logger.catch
def c(a, b=0):
    a / b


c(2)
