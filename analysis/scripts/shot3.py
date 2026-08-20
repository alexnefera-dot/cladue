from playwright.sync_api import sync_playwright
import os
errs=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None)
    pg=b.new_page(viewport={"width":1280,"height":1150})
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("file://"+os.path.abspath("report2.html")); pg.wait_for_timeout(900)
    tabs=pg.query_selector_all("nav button")
    print("tabs:", [t.inner_text() for t in tabs])
    pg.screenshot(path="r2_all.png")
    tabs[1].click(); pg.wait_for_timeout(400)
    pg.query_selector("tr.clk[data-b]").click(); pg.wait_for_timeout(300)
    pg.screenshot(path="r2_brands.png")
    tabs[2].click(); pg.wait_for_timeout(400); pg.screenshot(path="r2_cats.png")
    tabs[3].click(); pg.wait_for_timeout(400)
    pg.query_selector("tr.clk[data-sn]").click(); pg.wait_for_timeout(300)
    pg.evaluate("window.scrollTo(0,850)"); pg.wait_for_timeout(200)
    pg.screenshot(path="r2_g3.png")
    tabs[8].click(); pg.wait_for_timeout(400); pg.screenshot(path="r2_g2.png")
    print("overflow:", pg.evaluate("[document.body.scrollWidth, document.body.clientWidth]"))
    b.close()
print("ERRORS:", errs if errs else "none")
