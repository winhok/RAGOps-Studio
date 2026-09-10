#!/usr/bin/env python3
"""Exercise the compiled UI against an isolated, real local API installation.

Requires Playwright. The optional transport bridge only exists for environments
that cannot navigate a browser to localhost; it does not substitute RAG results.
"""
from pathlib import Path
import argparse
import atexit
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import httpx
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--transport-bridge',action='store_true')
args=parser.parse_args()
screens=ROOT/'assets/screenshots';screens.mkdir(parents=True,exist_ok=True)
(ROOT/'evidence').mkdir(exist_ok=True)
temporary=tempfile.TemporaryDirectory(prefix='ragops-browser-')
work=Path(temporary.name)
with socket.socket() as available:
 available.bind(('127.0.0.1',0));port=available.getsockname()[1]
env={**os.environ,'RAGOPS_STATE_DIR':str(work/'state'),'RAGOPS_PRINCIPALS_FILE':str(work/'identities/principals.json'),
 'RAGOPS_GRAPH_ENGINE':'python','RAGOPS_MODEL_PROVIDER':'local','RAGOPS_EMBEDDING_PROVIDER':'hash',
 'RAGOPS_RERANK_PROVIDER':'lexical','RAGOPS_VECTOR_BACKEND':'local','EMBEDDING_DIMENSIONS':'512',
 'RAGOPS_MAX_SEARCHES':'3','HOST':'127.0.0.1','PORT':str(port)}
subprocess.run([sys.executable,'scripts/bootstrap.py','--with-sample-data'],cwd=ROOT,env=env,check=True)
log=(work/'server.log').open('w')
process=subprocess.Popen([sys.executable,'scripts/serve.py'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
def cleanup():
 process.terminate()
 try:process.wait(timeout=5)
 except subprocess.TimeoutExpired:process.kill();process.wait()
 log.close();temporary.cleanup()
atexit.register(cleanup)
base_url=f'http://127.0.0.1:{port}'
for _ in range(60):
 try:
  if httpx.get(base_url+'/health',timeout=1).status_code==200:break
 except httpx.HTTPError:pass
 time.sleep(0.1)
else:raise RuntimeError('Local API failed to start')
lines=(work/'identities/access-credentials.txt').read_text().splitlines()
tokens={line.split(' |')[0]:lines[i+1] for i,line in enumerate(lines) if ' | tenant=' in line}

checks=[];errors=[]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH') or None,headless=True,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.on('console',lambda msg:errors.append('console:'+msg.text) if msg.type=='error' else None)
 if args.transport_bridge:
  # Browser networking is restricted in this environment. Exercise the unchanged
  # client logic through a local HTTP bridge instead of bypassing browser policy.
  # This is a transport harness, not a production server or a mocked RAG response.
  client=httpx.Client(base_url=base_url,timeout=60)
  def local_request(source,url,opts):
   response=client.request(opts.get('method','GET'),url,headers=opts.get('headers',{}),content=opts.get('body'))
   return {'status':response.status_code,'body':response.text}
  page.expose_binding('localRequest',local_request)
  page.set_content((ROOT/'frontend/dist/index.html').read_text().replace('<script type="module" src="/assets/app.js"></script>','').replace('<link rel="stylesheet" href="/assets/styles.css">',''))
  page.evaluate("""() => {
   const values=new Map();
   Object.defineProperty(window,'sessionStorage',{value:{getItem:k=>values.get(k)||null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)}});
   window.fetch=async (url,options={}) => {
     const result=await window.localRequest(url,{method:options.method||'GET',headers:Object.fromEntries(new Headers(options.headers).entries()),body:options.body});
     return new Response(result.body,{status:result.status,headers:{'Content-Type':'application/json'}});
   };
  }""")
  page.add_style_tag(content=(ROOT/'frontend/dist/assets/styles.css').read_text())
  api=(ROOT/'frontend/dist/assets/api.js').read_text().replace('export ','')
  app=(ROOT/'frontend/dist/assets/app.js').read_text()
  app='\n'.join(line for line in app.splitlines() if not line.startswith('import '))
  page.add_script_tag(type='module',content=api+'\n'+app)
  page.wait_for_selector('#login-form')
 else:
  page.goto(base_url,wait_until='networkidle')

 page.fill('#token',tokens['agentic-admin']);page.locator('#login-form button').click()
 page.wait_for_selector('#query-form')
 page.locator('#query-form button').click()
 page.wait_for_selector('.answer-panel .pill:text-is("answered")')
 assert page.locator('.source-card').count()==2
 checks.append('Multi-source query: answered with two bound citations')
 page.screenshot(path=str(screens/'01-workspace.png'),full_page=True)
 page.locator('.source-card').first.click()
 page.wait_for_selector('.source-content')
 assert '2000' in page.locator('.source-content').inner_text()
 checks.append('Bound citation opens its exact immutable stored source')
 page.locator('.modal-close').click()
 page.locator('[data-nav="trace"]').first.click()
 page.wait_for_selector('.round')
 assert page.locator('.round').count()==2
 page.screenshot(path=str(screens/'02-trace.png'),full_page=True)
 checks.append('Trace displays two actual retrieval rounds and scores')
 page.locator('[data-nav="ask"]').first.click()
 page.locator('[data-question="1"]').click();page.locator('#query-form button').click()
 page.wait_for_selector('.answer-panel .pill:text-is("clarify")')
 assert page.locator('.source-card').count()==0
 checks.append('Missing user amount asks clarification with zero citations')
 page.locator('[data-question="3"]').click();page.locator('#query-form button').click()
 page.wait_for_selector('.answer-panel .pill:text-is("refused")')
 checks.append('Superseded maintenance evidence correctly refuses')
 page.screenshot(path=str(screens/'03-refusal.png'),full_page=True)
 page.locator('[data-nav="evaluation"]').first.click()
 page.locator('[data-action="evaluate"]').click()
 page.wait_for_selector('.eval-stats')
 checks.append('Evaluation button executes actual server-side regression')
 page.locator('[data-action="signout"]').first.click()
 page.fill('#token',tokens['kb-support']);page.locator('#login-form button').click()
 page.wait_for_selector('#query-form')
 page.fill('#query','财务负责人需要复核哪些信息？');page.locator('#query-form button').click()
 page.wait_for_selector('.answer-panel .pill:text-is("refused")')
 page.locator('[data-nav="documents"]').first.click()
 assert page.locator('tbody tr').count()==2
 assert page.locator('[data-action="new-document"]').count()==0
 assert '财务对账' not in page.locator('tbody').inner_text()
 checks.append('Customer-service identity cannot read finance sources or edit documents')
 page.screenshot(path=str(screens/'04-scoped-library.png'),full_page=True)
 page.locator('[data-action="signout"]').first.click()
 page.fill('#token',tokens['kb-admin']);page.locator('#login-form button').click()
 page.wait_for_selector('#query-form')
 page.locator('[data-nav="documents"]').first.click()
 assert page.locator('tbody tr').count()==3
 page.locator('[data-edit="company-refund"]').click()
 page.wait_for_selector('#document-form')
 page.screenshot(path=str(screens/'05-document-editor.png'),full_page=True)
 checks.append('Administrator can open the document editor with ACL and revision inputs')
 page.locator('textarea[name="content"]').fill((ROOT/'data/updates/company-refund-v2.md').read_text())
 page.locator('#document-form button[type="submit"]').click() if page.locator('#document-form button[type="submit"]').count() else page.locator('#document-form .primary').click()
 page.wait_for_selector('.banner.success')
 assert page.locator('tr').filter(has=page.locator('[data-edit="company-refund"]')).locator('.revision').inner_text()=='v2'
 checks.append('Document editor publishes the supplied version update through the actual API')
 page.locator('[data-edit="company-refund"]').click()
 page.wait_for_selector('#document-form')
 page.locator('#document-form .primary').click()
 page.wait_for_selector('.banner.success')
 assert 'skipped' in page.locator('.banner.success').inner_text().lower()
 checks.append('Identical publication is skipped without creating a third revision')
 page.locator('[data-history="company-refund"]').click()
 page.wait_for_selector('.history-row')
 assert page.locator('.history-row').count()==2
 checks.append('Version-history view shows persisted source revision')
 page.locator('.modal-close').click()
 page.locator('[data-nav="ask"]').first.click()
 page.fill('#query','退款金额超过多少元需要人工审核？');page.locator('#query-form button').click()
 page.wait_for_selector('.answer-panel .pill:text-is("answered")')
 assert '5000' in page.locator('.answer-text').inner_text()
 assert '3000' not in page.locator('.answer-text').inner_text()
 checks.append('Question after update uses only the latest 5000 CNY source revision')
 page.fill('#query','财务负责人需要复核哪些信息？');page.locator('#query-form button').click()
 page.wait_for_selector('.answer-panel .pill:text-is("answered")')
 assert '原支付渠道' in page.locator('.answer-text').inner_text()
 checks.append('Tenant administrator can answer the same restricted finance question')
 page.set_viewport_size({'width':390,'height':844})
 page.screenshot(path=str(screens/'06-mobile.png'),full_page=True)
 overflow=page.evaluate('document.documentElement.scrollWidth>window.innerWidth')
 checks.append('Mobile document width fits viewport' if not overflow else 'MOBILE_OVERFLOW')
 browser.close()
report={'checks':checks,'browser_errors':errors,'browser': 'Chromium with local HTTP transport bridge' if args.transport_bridge else 'Chromium direct HTTP navigation', 'remote_llm_used':False}
(ROOT/'evidence/browser-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))
assert not errors
assert not overflow
