"""Opt-in, process-local cache warming. No UI or authentication operations."""
import logging
import os
import threading
import time

_lock = threading.Lock()
_thread = None
_log = logging.getLogger(__name__)


def execute(name, task):
    started = time.monotonic()
    try:
        task()
        _log.warning('MacroFX preload %s: %.2fs', name, time.monotonic()-started)
    except Exception:
        _log.exception('MacroFX preload %s failed; normal loading remains available', name)


def warm_gold():
    from metals_data import load_gold_data
    from gold_cot import load_gold_cot
    data, sources, errors = load_gold_data()
    _log.warning('MacroFX preload gold sources: %s series; %s notices', len(data), len(errors))
    execute('gold COT', load_gold_cot)


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
            if os.getenv('MACROFX_PRELOAD_V4', '0') != '1':
                while True:
                    for name, task in [('banks', warm_banks), ('scores', warm_scores)]:
                        execute(name, task)
                    time.sleep(240)
            # One worker; preserve V3 cadence, interleave incremental FX work.
            next_core = next_gold = next_fx = 0.0
            fx_steps = None
            while True:
                now = time.monotonic()
                if now >= next_core:
                    execute('banks', warm_banks)
                    execute('scores', warm_scores)
                    next_core = time.monotonic() + 240
                elif now >= next_gold:
                    execute('gold', warm_gold)
                    next_gold = time.monotonic() + 600
                elif fx_steps is None and now >= next_fx:
                    try:
                        from fx_divergences import warm_rank_steps
                        fx_steps = warm_rank_steps()
                    except Exception:
                        _log.exception('MacroFX preload divergences initialization failed')
                        next_fx = time.monotonic() + 1800
                elif fx_steps is not None:
                    try:
                        next(fx_steps)
                    except StopIteration:
                        fx_steps = None
                        next_fx = time.monotonic() + 1800
                    except Exception:
                        _log.exception('MacroFX preload divergences failed')
                        fx_steps = None
                        next_fx = time.monotonic() + 1800
                time.sleep(1)
        _thread = threading.Thread(target=run, name='macrofx-preload', daemon=True)
        _thread.start()
