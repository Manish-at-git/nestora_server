"""Small standard-library logging setup; structured logging can plug in here later."""

import logging


def configure_logging(debug: bool) -> None:
    """Configure one predictable console logger without logging secrets or request bodies."""
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
