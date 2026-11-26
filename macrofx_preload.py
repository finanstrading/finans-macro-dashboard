"""Opt-in, process-local cache warming. No UI or authentication operations."""
import logging
import os
import threading
import time

_lock = threading.Lock()
_thread = None
_log = logging.getLogger(__name__)


def start_preload(warm_scores, warm_banks):
    global _thread
    if os.getenv('MACROFX_PRELOAD', '0') != '1':
        return
    with _lock:
        if _thread is not None and _thread.is_alive():
            return
        def run():
            # Give the initial interactive request priority.
            time.sleep(15)
            while True:
                for name, task in [('banks', warm_banks), ('scores', warm_scores)]:
                    started = time.monotonic()
                    try:
                        task()
                        _log.warning('MacroFX preload %s: %.2fs', name, time.monotonic()-started)
                    except Exception:
                        _log.exception('MacroFX preload %s failed; normal loading remains available', name)
                time.sleep(240)
        _thread = threading.Thread(target=run, name='macrofx-preload', daemon=True)
        _thread.start()
