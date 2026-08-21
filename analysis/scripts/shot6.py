from playwright.sync_api import sync_playwright
import os
errs=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None)
    pg=b.new_page(viewport={"width":1400,"height":1150})
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("file://"+os.path.abspath("report3.html")); pg.wait_for_timeout(1200)
    tabs=pg.query_selector_all("nav button")
    print("tabs:", [t.inner_text() for t in tabs])
    pg.screenshot(path="w_over.png")
    for i,nm in [(1,"all"),(2,"lead"),(3,"zones"),(4,"brands"),(5,"cats")]:
        tabs[i].click(); pg.wait_for_timeout(600); pg.screenshot(path=f"w_{nm}.png")
    tabs[1].click(); pg.wait_for_timeout(500)
    pg.query_selector("tr.clk[data-i]").click(); pg.wait_for_timeout(400)
    pg.evaluate("window.scrollTo(0,420)"); pg.wait_for_timeout(200); pg.screenshot(path="w_exp.png")
    tabs[2].click(); pg.wait_for_timeout(400)
    pg.query_selector("button.more").click(); pg.wait_for_timeout(400)
    pg.evaluate("window.scrollTo(0,300)"); pg.wait_for_timeout(200); pg.screenshot(path="w_leadk.png")
    print("overflow:", pg.evaluate("[document.body.scrollWidth, document.body.clientWidth]"))
    b.close()
print("ERRORS:", errs if errs else "none")
