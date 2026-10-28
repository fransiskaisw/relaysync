"""Bagian bersama antarmuka baris perintah: logging, runtime, sinyal berhenti."""
from __future__ import annotations

import logging
import signal
import sys
import threading

from relaysync.settings import ConfigError, Runtime, load_runtime

EXIT_CONFIG = 2


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def runtime_or_exit(config: str | None, env_file: str) -> Runtime:
    """Muat konfigurasi; bila TEAM_ID placeholder, cetak saran dan keluar."""
    try:
        return load_runtime(config, env_file)
    except ConfigError as exc:
        print(f"RELAYSYNC menolak berjalan: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_CONFIG) from exc


def stop_on_signal() -> threading.Event:
    """Event yang di-set saat Ctrl+C atau SIGTERM."""
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda _signum, _frame: stop.set())
    return stop
