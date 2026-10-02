"""Logging config shared by all entrypoints."""

from __future__ import annotations

import logging


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("httpx", "httpcore", "urllib3", "huggingface_hub"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
