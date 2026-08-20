from playwright.sync_api import sync_playwright
import os
errs=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None)
    pg=b.new_page(viewport={"width":1280,"height":1150})
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("file://"+os.path.abspath("report2.html")); pg.wait_for_timeout(1000)
    tabs=pg.query_selector_all("nav button")
    print("tabs:", [t.inner_text() for t in tabs])
    pg.screenshot(path="f_all.png")
    for i,nm in [(1,"night"),(2,"day"),(3,"gen"),(4,"brands"),(5,"cats")]:
        tabs[i].click(); pg.wait_for_timeout(500); pg.screenshot(path=f"f_{nm}.png")
    tabs[2].click(); pg.wait_for_timeout(400)
    pg.evaluate("window.scrollTo(0,2600)"); pg.wait_for_timeout(250); pg.screenshot(path="f_day2.png")
    tabs[1].click(); pg.wait_for_timeout(400)
    pg.query_selector("tr.clk[data-g]").click(); pg.wait_for_timeout(400)
    pg.evaluate("window.scrollTo(0,600)"); pg.wait_for_timeout(200); pg.screenshot(path="f_exp.png")
    print("overflow:", pg.evaluate("[document.body.scrollWidth, document.body.clientWidth]"))
    b.close()
print("ERRORS:", errs if errs else "none")
