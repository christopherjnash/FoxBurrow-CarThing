"""Bounded browser recovery and an offline page; independent of optional integrations."""
import os
import signal
import subprocess
import time
from collections import deque
from urllib.parse import quote, urlsplit
import requests

OFFLINE_URL = 'data:text/html;charset=utf-8,' + quote('''<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><title>Reconnecting</title><style>body{background:#14211c;color:#fff;font:28px system-ui;display:grid;place-content:center;height:90vh;text-align:center}p{font-size:18px}</style><h1>Reconnecting…</h1><p>Your display will return when the connection is available.</p>''')


def browser_command(binary, args):
    """The browser gets neither root privileges nor a disabled sandbox."""
    return ['runuser', '-u', 'wallthing-browser', '--', 'env', 'HOME=/home/wallthing-browser', binary, *args]


def supervise_process(command, stopped, logfile, logger, *, popen=subprocess.Popen, clock=time.monotonic, fatal=os._exit):
    failures = deque()
    while not stopped.is_set():
        started = clock()
        process = popen(command, stdout=logfile, stderr=logfile, start_new_session=True)
        while process.poll() is None:
            if stopped.wait(0.5):
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=5)
                except ProcessLookupError:
                    pass
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
                return
        if stopped.is_set():
            return
        now = clock()
        while failures and now - failures[0] > 300:
            failures.popleft()
        failures.append(now)
        logger.warning('Browser exited; retrying with backoff')
        if len(failures) >= 5:
            logger.error('Browser exited five times within five minutes; handing recovery to systemd')
            fatal(1)
            return
        if now - started >= 300:
            failures.clear()
        if stopped.wait(min(2 ** max(len(failures), 1), 30)):
            return


def reachable(url, get=requests.get):
    parsed = urlsplit(url)
    if parsed.scheme not in ('https', 'http') or not parsed.netloc:
        return False
    try:
        # Any non-server-error response proves connectivity, including auth redirects.
        # Stream and close so large pages never accumulate in memory.
        response = get(url, timeout=(3, 5), allow_redirects=False, stream=True)
        try:
            return response.status_code < 500
        finally:
            response.close()
    except requests.RequestException:
        return False


def recover_connection(browser, stopped, check=reachable):
    offline = False
    failures = 0
    previous_url = None
    while not stopped.wait(10):
        url = browser.config.get('url')
        if url != previous_url:
            failures = 0
            previous_url = url
        if check(url):
            failures = 0
            if offline:
                try:
                    browser.chromium_navigate(url)
                    offline = False
                except Exception:
                    browser.log.warning('Browser not ready for reconnect yet')
        else:
            failures += 1
            if failures >= 3:
                try:
                    # Reapply after a browser crash while the server is still unavailable.
                    browser.chromium_navigate(OFFLINE_URL)
                    offline = True
                except Exception:
                    browser.log.warning('Browser not ready for offline page yet')
