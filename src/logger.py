import logging
from pathlib import Path


def setup_logger(project_root: Path) -> logging.Logger:
    """
    Creates and returns an application logger.
    Logs are printed to console and saved into output/app.log.
    """

    output_dir = project_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    log_file = output_dir / "app.log"

    logger = logging.getLogger("collections_email_automation")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers when running multiple times
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger