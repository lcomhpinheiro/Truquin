import json
from pathlib import Path
import argparse

parser=argparse.ArgumentParser(description="Teste de integração em navegador (Playwright opcional).")
parser.add_argument("--url", default="http://localhost:8765")
parser.add_argument("--browser", help="Caminho opcional de um navegador Chromium instalado")
args=parser.parse_args()
base_url=args.url.rstrip("/")
output=Path("test-results")
output.mkdir(exist_ok=True)
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=args.browser, headless=True)
    errors=[]
    context=browser.new_context(viewport={'width':1440,'height':1050})
    page=context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(base_url)
    page.wait_for_selector('#rooms .empty-state, #rooms .room-item')
    page.screenshot(path=str(output/'home-desktop.png'),full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.locator('#nickname').fill('Ana')
    page.locator('#room-name').fill('Resenha de hoje')
    page.locator('#create-form button[type=submit]').click()
    page.wait_for_selector('#game:not([hidden])')
    code=page.locator('#invite-code').inner_text()
    clients=[page]
    for name in ['Bia','Caio','Dani']:
        ctx=browser.new_context(viewport={'width':1280,'height':900})
        pg=ctx.new_page()
        pg.on('pageerror', lambda error: errors.append(str(error)))
        pg.goto(base_url+'/?mesa='+code)
        pg.locator('#nickname').fill(name)
        pg.locator('#join-form button[type=submit]').click()
        pg.wait_for_selector('#game:not([hidden])')
        clients.append(pg)
    page.locator('#start').click()
    page.wait_for_selector('#hand .card-button')
    assert len(page.locator('#hand .card-button').all())==3
    page.locator('#raise').click()
    clients[1].locator('#accept').wait_for(state='visible')
    clients[1].locator('#accept').click()
    page.wait_for_function("document.querySelector('#table-stake').textContent.includes('3 PONTOS')")
    page.screenshot(path=str(output/'game-desktop.png'),full_page=True)
    for client in clients:
        client.locator('#hand .card-button:not([disabled])').first.wait_for()
        client.locator('#hand .card-button:not([disabled])').first.click()
    page.wait_for_function("document.querySelectorAll('#table-cards img').length===4")
    assert all(pg.locator('#hand .card-button').count()==2 for pg in clients)
    token=page.evaluate("JSON.parse(sessionStorage.getItem('truco-session')).token")
    page.reload()
    page.wait_for_selector('#game:not([hidden])')
    assert page.evaluate("JSON.parse(sessionStorage.getItem('truco-session')).token")==token
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path=str(output/'game-mobile.png'),full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Game overflows mobile'
    mobile=browser.new_context(viewport={'width':390,'height':844}).new_page()
    mobile.goto(base_url)
    mobile.screenshot(path=str(output/'home-mobile.png'),full_page=True)
    assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Home overflows mobile'
    mobile.locator('#rules-open').click()
    assert mobile.locator('#rules').evaluate('(el)=>el.open')
    mobile.locator('#rules-close').click()
    clients[1].locator('#leave').click()
    clients[1].wait_for_selector('#home:not([hidden])')
    page.wait_for_function("Array.from(document.querySelectorAll('.seat-note')).some(el=>el.textContent==='BOT')")
    assert not errors, errors
    print(json.dumps({'four_clients':True,'truco_accepted':True,'four_cards_played':True,'reload_reconnect':True,'mobile_no_overflow':True,'leave_bot_takeover':True,'javascript_errors':errors}))
    # Remove test room without leaving the user's lobby cluttered.
    for pg in [clients[0],clients[2],clients[3]]:
        pg.locator('#leave').click()
        pg.wait_for_selector('#home:not([hidden])')
    browser.close()
