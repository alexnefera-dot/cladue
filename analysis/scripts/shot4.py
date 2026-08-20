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
    tabs[1].click(); pg.wait_for_timeout(500)
    pg.screenshot(path="ev_a.png")
    pg.evaluate("window.scrollTo(0,1000)"); pg.wait_for_timeout(250); pg.screenshot(path="ev_b.png")
    pg.evaluate("window.scrollTo(0,2050)"); pg.wait_for_timeout(250); pg.screenshot(path="ev_c.png")
    pg.evaluate("window.scrollTo(0,0)"); pg.wait_for_timeout(200)
    pg.query_selector("tr.clk[data-e]").click(); pg.wait_for_timeout(400)
    pg.evaluate("window.scrollTo(0,420)"); pg.wait_for_timeout(200); pg.screenshot(path="ev_exp.png")
    print("overflow:", pg.evaluate("[document.body.scrollWidth, document.body.clientWidth]"))
    b.close()
print("ERRORS:", errs if errs else "none")
