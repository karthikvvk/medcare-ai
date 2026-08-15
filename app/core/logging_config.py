import logging
import sys

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("medcare_app.log", encoding="utf-8")
        ]
    )
    logger = logging.getLogger("medcare")
    logger.setLevel(logging.INFO)
    return logger

logger = setup_logging()
