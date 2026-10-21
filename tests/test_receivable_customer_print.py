import json
import re
import shutil
import subprocess

import pytest

from utils.receivable_report import render_statement_print


@pytest.mark.parametrize("stock", ["standard", "triplicate", "a4_driver"])
def test_print_customer_selects_all_customer_pages_and_resets(stock):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required to exercise the preview print handlers")
    html = render_statement_print([], paper_stock=stock)
    assert 'id="print-customer"' in html
    assert '.preview-stage>.print-omit{display:none!important}' in html
    assert '.preview-stage>.print-customer-offset{position:relative;left:2mm}' in html
    script = re.search(r'<script id="statement-customer-print">(.*?)</script>', html, re.S)[1]
    # Model the real top-level sheet elements, including stock wrappers.
    harness = '''
const assert=require('node:assert/strict');
const wrapped=WRAPPED;
const sheets=['RA01','RB02','RA01'].map(id=>{
  const classes=new Set();
  const customer={dataset:{customerId:id}};
  const heading={textContent:'佳咊實業有限公司'};
  return {dataset:customer.dataset,heading,
    matches:()=>!wrapped,querySelector:selector=>selector==='h1'?heading:customer,
    classes,classList:{remove:(...names)=>names.forEach(n=>classes.delete(n)),
      add:n=>classes.add(n),toggle:(n,on)=>on?classes.add(n):classes.delete(n)}};
});
let current=2;
const listeners={};
const printed=[];
const companies=[{value:'佳咊實業有限公司'},{value:'加舜企業有限公司'}];
const dialog={open:false,querySelectorAll:()=>companies,
  querySelector:selector=>selector==='input'?companies[0]:companies.find(c=>c.checked),
  showModal(){this.open=true},close(){this.open=false}};
const document={getElementById:()=>dialog};
const window={addEventListener:(name,fn)=>listeners[name]=fn,
  print:()=>printed.push(sheets.map(p=>!p.classes.has('print-omit')))};
SCRIPT
printCustomer();
assert(dialog.open);
assert.equal(printed.length,0);
assert(companies[0].checked);
dialog.close();
assert(sheets.every(p=>p.classes.size===0));
printCustomer();
companies[0].checked=false;companies[1].checked=true;
confirmCustomerPrint();
assert(!dialog.open);
assert.deepEqual(printed.pop(),[true,false,true]);
assert.deepEqual(sheets.map(p=>p.heading.textContent),['加舜企業有限公司','佳咊實業有限公司','加舜企業有限公司']);
assert(sheets[2].classes.has('print-last'));
assert.deepEqual(sheets.map(p=>p.classes.has('print-customer-offset')),[true,false,true]);
listeners.afterprint();
assert(sheets.every(p=>p.classes.size===0));
assert(sheets.every(p=>p.heading.textContent==='佳咊實業有限公司'));
current=1;
printCustomer();
confirmCustomerPrint();
assert.deepEqual(printed.pop(),[false,true,false]);
assert(sheets[1].classes.has('print-last'));
assert.deepEqual(sheets.map(p=>p.classes.has('print-customer-offset')),[false,true,false]);
printAll();
assert.deepEqual(printed.pop(),[true,true,true]);
assert(sheets.every(p=>p.classes.size===0));
window.print=()=>{throw new Error('cancelled')};
assert.throws(()=>printSelectedCustomer('加舜企業有限公司'));
assert(sheets.every(p=>p.classes.size===0));
assert(sheets.every(p=>p.heading.textContent==='佳咊實業有限公司'));
'''.replace("WRAPPED", json.dumps(stock != "standard")).replace("SCRIPT", script)
    subprocess.run([node, "-e", harness], check=True, capture_output=True, text=True)
