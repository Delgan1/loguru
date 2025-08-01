import sys

from loggerex import logger

logger.remove()
logger.add(sys.stderr, format="", diagnose=False, backtrace=False, colorize=False)


with logger.catch():
    1 / 0
