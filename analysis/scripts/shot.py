from playwright.sync_api import sync_playwright
import sys
errs=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/opt/pw-browsers/chromium" if __import__('os').path.exists("/opt/pw-browsers/chromium") else None)
    pg=b.new_page(viewport={"width":1280,"height":1000})
    pg.on("console", lambda m: errs.append(m.type+": "+m.text) if m.type=="error" else None)
    pg.on("pageerror", lambda e: errs.append("pageerror: "+str(e)))
    pg.goto("file://"+__import__('os').path.abspath("report.html"))
    pg.wait_for_timeout(1200)
    pg.screenshot(path="shot_itog.png", full_page=False)
    tabs=pg.query_selector_all("nav button")
    print("tabs:", [t.inner_text() for t in tabs])
    for i,name in [(1,"run"),(2,"age"),(4,"zone"),(5,"cut"),(8,"new")]:
        tabs[i].click(); pg.wait_for_timeout(500)
        pg.screenshot(path=f"shot_{name}.png", full_page=False)
    # expand a row
    tabs[1].click(); pg.wait_for_timeout(300)
    r=pg.query_selector("#runbody tr.clk"); r.click(); pg.wait_for_timeout(300)
    pg.screenshot(path="shot_expand.png")
    print("body scrollWidth vs clientWidth:", pg.evaluate("[document.body.scrollWidth, document.body.clientWidth]"))
    b.close()
print("ERRORS:", errs if errs else "none")
