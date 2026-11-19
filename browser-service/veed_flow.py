"""The click-by-click VEED flow.

This file is still a placeholder: the steps have to come from your own VEED account.
  1. Run ./record.sh, log in to VEED if asked, and make one video the way you normally do.
     Paste any placeholder script text where the script goes.
  2. Click the export/download button and let the MP4 download.
  3. Close the window. The recording is saved to recordings/veed_recording.py.
Claude then turns that recording into run() below.
"""
from __future__ import annotations

import pathlib
import time

from playwright.sync_api import Page


def remaining_ms(deadline: float) -> int:
    left = int((deadline - time.time()) * 1000)
    if left <= 0:
        raise TimeoutError("VEED job exceeded VEED_JOB_TIMEOUT_MIN")
    return left


def run(page: Page, script: str, title: str, out: pathlib.Path, deadline: float) -> None:
    """Create a VEED video that speaks `script`, then save the MP4 to `out`.

    Expected shape once the recording is adapted:

        page.goto("https://www.veed.io/workspaces/...", wait_until="domcontentloaded")  # "load" is very slow on VEED
        ...                                   # recorded clicks
        page.get_by_role("textbox", name="...").fill(script)
        ...                                   # generate / render
        with page.expect_download(timeout=remaining_ms(deadline)) as dl:
            page.get_by_role("button", name="Download").click()
        dl.value.save_as(out)
    """
    raise NotImplementedError(
        "VEED flow not recorded yet: run browser-service/record.sh, then ask Claude to adapt the recording"
    )
