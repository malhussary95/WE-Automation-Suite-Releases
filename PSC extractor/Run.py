# WE PSC Extractor - Web backend only
import json
import pandas as pd
from playwright.sync_api import sync_playwright

CONFIG_FILE = "config.json"

def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except Exception: return {"username":"","password":"","domain":"CAIRO.TELECOMEGYPT.CORP"}

def save_config(username,password,domain):
    with open(CONFIG_FILE,"w",encoding="utf-8") as f:
        json.dump({"username":username,"password":password,"domain":domain},f,indent=4,ensure_ascii=False)

def run_extraction(file_path, username=None, password=None, domain=None, log=print, output_file="PSC_Output.xlsx"):
    cfg=load_config(); username=(username or cfg.get("username","")).strip(); password=(password or cfg.get("password","")).strip(); domain=(domain or cfg.get("domain","CAIRO.TELECOMEGYPT.CORP")).strip()
    if not username or not password: raise ValueError("PSC username and password are required")
    df=pd.read_excel(file_path)
    if "ID" not in df.columns: raise ValueError("Excel file must contain column named: ID")
    ids=df["ID"].dropna().astype(str).tolist()
    if not ids: raise ValueError("No IDs found in Excel")
    save_config(username,password,domain); results=[]
    log("🌐 Opening ESC/P portal…")
    with sync_playwright() as p:
        browser=p.chromium.launch(channel="chrome",headless=True,args=["--disable-blink-features=AutomationControlled"])
        context=browser.new_context(viewport={"width":1920,"height":1080}); page=context.new_page()
        page.goto("https://escp.te.eg",wait_until="domcontentloaded")
        page.fill('input[name="j_username"]',username); page.fill('input[name="j_password"]',password); page.select_option('select[name="domain"]',label=domain); page.locator("#loginSDPage").click()
        page.wait_for_url(lambda url:"HomePage" in url or "my_view" in url,timeout=60000)
        total=len(ids)
        for i,rid in enumerate(ids,1):
            log(f"Processing {i}/{total} -> {rid}")
            try:
                response=context.request.get(f"https://escp.te.eg/api/v3/requests/{rid}",headers={"apiclient":"sdp_web","portalid":"1","x-requested-with":"XMLHttpRequest","accept":"application/json, text/javascript, */*; q=0.01","referer":f"https://escp.te.eg/WorkOrder.do?woMode=viewWO&woID={rid}"})
                if response.status!=200: results.append({"ID":rid,"Status":response.status}); continue
                d=response.json().get("request",{}); udf=d.get("udf_fields",{}); cb=d.get("created_by",{}); ct=d.get("created_time",{})
                results.append({"ID":rid,"change title":d.get("subject",""),"MSAN Code":udf.get("udf_sline_328",""),"MSAN IP":udf.get("udf_sline_329",""),"vendor":udf.get("udf_pick_316",""),"POP":udf.get("udf_pick_320",""),"MSAN Status":udf.get("udf_pick_315",""),"Transmission Media":udf.get("udf_pick_323",""),"Circuit Status":udf.get("udf_pick_308",""),"Cut status":udf.get("udf_pick_310",""),"Cut Reason":udf.get("udf_pick_311",""),"create date":ct.get("display_value",""),"Created by name":cb.get("name","")})
            except Exception as e: results.append({"ID":rid,"Error":str(e)})
        browser.close()
    pd.DataFrame(results).to_excel(output_file,index=False); log(f"✅ Finished. Saved {len(results)} records to {output_file}"); return output_file

if __name__ == "__main__":
    print("This module is web-only. Start the application with start.py or start_web.bat.")
