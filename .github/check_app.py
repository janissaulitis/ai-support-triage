"""Opens the live app in a real browser. Mode "wake": just make sure it is awake.
Mode "test": also sort the inbox and run the 96-email accuracy test, saving screenshots and page text."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://ai-inbox-triage.streamlit.app/"
mode = sys.argv[1] if len(sys.argv) > 1 else "wake"


def save_run(app, page, name):
    """Click the visible "Download this run" button and keep the JSON, if the app offered one (live runs only)."""
    btn = app.get_by_role("button", name="Download this run (JSON)").locator("visible=true")
    if not btn.count():
        print(f"{name}: no live run to save")
        return
    with page.expect_download(timeout=60_000) as d:
        btn.first.click()
    d.value.save_as(str(out / f"{name}.json"))
    print(f"{name}: saved")
out = Path("out"); out.mkdir(exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1366, "height": 900}, color_scheme="dark")
    page.goto(URL, timeout=120_000)
    page.wait_for_timeout(8_000)
    wake = page.get_by_role("button", name="Yes, get this app back up!")
    if wake.count():
        print("was asleep, waking up"); wake.click(); page.wait_for_timeout(90_000)
    app = page.frame_locator("iframe[title='streamlitApp']")
    app.locator(".k-name, h1").first.wait_for(timeout=180_000)
    print("awake:", app.locator(".k-name, h1").first.inner_text())
    if mode == "test":
      try:
        app.get_by_role("button", name="Sort the inbox").click()
        err = app.locator("[data-testid=stAlertContentError]").or_(app.locator("[data-testid=stException]"))
        app.get_by_text("Open an email to see the draft reply").or_(err).first.wait_for(timeout=420_000)
        if app.locator("[data-testid=stAlertContentError], [data-testid=stException]").count():
            raise RuntimeError("app error: " + app.locator("[data-testid=stAlertContentError], [data-testid=stException]").first.inner_text()[:800])
        page.wait_for_timeout(2_000)
        page.screenshot(path=str(out / "1_inbox.png"), full_page=True)
        save_run(app, page, "inbox")
        (out / "1_inbox.txt").write_text(app.locator("[data-testid=stMain]").inner_text())
        app.get_by_role("tab", name="Accuracy test").click()
        app.get_by_role("button", name="Run the test").click()
        app.get_by_text("Where it disagreed").or_(err).first.wait_for(timeout=900_000)
        if err.count():
            raise RuntimeError("app error: " + err.first.inner_text()[:800])
        page.wait_for_timeout(3_000)
        page.screenshot(path=str(out / "2_test.png"), full_page=True)
        save_run(app, page, "test")
        (out / "2_test.txt").write_text(app.locator("[data-testid=stMain]").inner_text())
        print("test finished")
      except Exception as e:
        print("FAILED:", str(e)[:1000])
        page.screenshot(path=str(out / "error.png"), full_page=True)
        try:
            (out / "error.txt").write_text(app.locator("[data-testid=stMain]").inner_text())
        except Exception:
            pass
        raise
    b.close()
