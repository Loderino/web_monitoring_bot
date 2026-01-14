import logging
from logging.handlers import RotatingFileHandler

from constants import LOGS_DIR


def get_logger(name, level=logging.DEBUG) -> logging.Logger:
    """
    Create and configure a RotatingFileHandler logger with the given name and log level.
    Max bytes in one log file is 10 Mb

    Args:
        name (str): The name of the logger.
        level (int, optional): The log level for the logger. Defaults to logging.INFO.

    Returns:
        logging.Logger: The configured logger.

    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    file_path = LOGS_DIR / f"{name}.log"
    file_handler = RotatingFileHandler(file_path.as_posix(), maxBytes=10 * 1024 * 1024, backupCount=10)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s [in %(pathname)s:%(lineno)d]")
    )
    file_handler.setLevel(level)
    logger = logging.getLogger(name)
    logger.addHandler(file_handler)
    logger.setLevel(level)
    return logger
