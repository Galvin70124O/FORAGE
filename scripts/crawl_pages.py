"""Open every FORAGE page with every data source and report exceptions, warnings and console errors.

Dev tool (needs `pip install playwright` and `python -m playwright install chromium`; not in requirements.txt).

    python scripts/crawl_pages.py --url http://localhost:8501 --out shots --modes light dark --widths 1440 390
    python scripts/crawl_pages.py --url ... --exercise   # also logs a purchase and a pantry check

Exit code 1 if any page shows an exception, a browser console error or a Vega warning.
"""

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

INSIGHTS = ["Overview", "Data Quality", "EDA", "Waste & Expiry", "Forecasting", "Recommendations"]
PERSONAL = ["Home", "I bought", "Pantry check", "Shopping list", "My data"]
TO_KITCHEN, TO_INSIGHTS = "Back to Kitchen", "Open Project insights"
SOURCES = ["Demo data", "My data", "M5 (Walmart)", "Instacart"]
PHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Mobile/15E148 Safari/604.1")


def settle(page, extra_ms=1500):
    page.wait_for_timeout(500)
    for _ in range(360):  # up to 3 minutes for first-time model training
        busy = page.locator('[data-testid="stStatusWidget"]').count() + page.locator('[data-testid="stSpinner"]').count()
        if not busy:
            break
        page.wait_for_timeout(500)
    page.wait_for_timeout(extra_ms)


def open_sidebar(page):
    if page.locator('[data-testid="stSidebar"][aria-expanded="true"]').count():
        return
    for selector in ('[data-testid="stExpandSidebarButton"]', '[data-testid="stSidebarCollapsedControl"] button'):
        control = page.locator(selector)
        if control.count():
            control.first.click()
            page.wait_for_timeout(600)
            return


def goto(page, name):
    open_sidebar(page)
    page.locator('[data-testid="stSidebar"] a').filter(has_text=name).first.click()
    settle(page)


def switch_mode(page, kitchen: bool) -> None:
    """Use the switch at the bottom of the sidebar (no-op when already in that mode)."""
    open_sidebar(page)
    button = (page.locator('[data-testid="stSidebar"] [data-testid^="stBaseButton"]')
              .filter(has_text=TO_KITCHEN if kitchen else TO_INSIGHTS).locator("visible=true"))
    if button.count():
        button.first.click()
        settle(page)


def choose_source(page, source):
    open_sidebar(page)
    option = page.locator('[data-testid="stSidebar"] [data-testid="stRadio"] label').filter(has_text=source)
    if not option.count():
        return False
    option.first.click()
    settle(page)
    return True


def check(page, label, console, results):
    exceptions = page.locator('[data-testid="stException"]').all_inner_texts()
    problems = [f"exception: {e[:300]}" for e in exceptions] + [f"console: {c[:300]}" for c in console]
    results.append((label, problems))
    print(("OK      " if not problems else "PROBLEM ") + label)
    for problem in problems:
        print("    " + problem.replace("\n", " | "))
    console.clear()


def exercise(page, console, results):
    """Log a purchase with a tile, then do a pantry check with a level button (proves writes work here)."""
    switch_mode(page, kitchen=True)
    goto(page, "I bought")
    page.get_by_role("button", name="Milk", exact=True).first.click()
    settle(page)
    page.get_by_role("button", name="Save", exact=True).click()
    settle(page)
    saved = page.locator('[data-testid="stAlertContentSuccess"]').filter(has_text="Saved: Milk").count()
    check(page, "exercise | I bought: save" + ("" if saved else " (no success message)"), console, results)
    if not saved:
        results[-1][1].append("no 'Saved: Milk' message after Save")
    goto(page, "Pantry check")
    page.get_by_role("button", name="Check everything").first.click()
    settle(page)
    page.get_by_role("button", name="Half", exact=True).first.click()
    settle(page)
    check(page, "exercise | Pantry check: Half", console, results)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8501")
    parser.add_argument("--out", type=Path, default=Path("crawl_shots"))
    parser.add_argument("--modes", nargs="+", default=["light"])
    parser.add_argument("--widths", nargs="+", type=int, default=[1440])
    parser.add_argument("--sources", nargs="+", default=SOURCES)
    parser.add_argument("--pages", nargs="+", default=INSIGHTS + PERSONAL)
    parser.add_argument("--exercise", action="store_true")
    parser.add_argument("--full-page", action="store_true", help="tall viewport so screenshots show the whole page")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for mode in args.modes:
            for width in args.widths:
                height = 2600 if args.full_page else (900 if width > 600 else 844)
                phone = width < 600  # present as a phone so the navigation behaves as on a real device
                context = browser.new_context(
                    viewport={"width": width, "height": height}, color_scheme=mode, is_mobile=phone, has_touch=phone,
                    device_scale_factor=2 if phone else 1,
                    user_agent=PHONE_UA if phone else None)
                page = context.new_page()
                console = []
                page.on("console", lambda m, console=console: console.append(f"{m.type}: {m.text}")
                        if m.type == "error" or (m.type == "warning" and "WARN" in m.text) else None)
                page.on("pageerror", lambda e, console=console: console.append(f"pageerror: {e}"))
                page.goto(args.url)
                # a cold start (fresh environment) can take a while before anything renders
                page.wait_for_selector('[data-testid="stSidebar"] a', timeout=240_000)
                settle(page, 2500)
                def shoot(label, page=page, console=console):
                    tag = label.replace(" | ", "_").replace(" ", "_").replace("&", "and").replace("(", "").replace(")", "")
                    page.screenshot(path=str(args.out / f"{tag}.png"))
                    check(page, label, console, results)

                # Kitchen pages (a visitor sees the sign-in page there)
                switch_mode(page, kitchen=True)
                for name in [n for n in args.pages if n in PERSONAL]:
                    goto(page, name)
                    skip = page.locator('[data-testid="stMain"] button').filter(has_text="Skip")
                    if name == "Home" and skip.count():  # first-time walkthrough
                        shoot(f"{mode} {width} | Kitchen | Home walkthrough")
                        skip.first.click()
                        settle(page)
                    shoot(f"{mode} {width} | Kitchen | {name}")
                if args.exercise and mode == args.modes[0] and width == args.widths[0]:
                    exercise(page, console, results)
                # Project insights pages, per data source
                switch_mode(page, kitchen=False)
                for source in args.sources:
                    if not choose_source(page, source):
                        print(f"skip    {mode} {width} | {source} (not offered in this session)")
                        continue
                    for name in [n for n in args.pages if n in INSIGHTS]:
                        goto(page, name)
                        shoot(f"{mode} {width} | {source} | {name}")
                page.close()
                context.close()
        browser.close()
    failed = [label for label, problems in results if problems]
    print(f"\n{len(results)} checks, {len(failed)} with problems")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
