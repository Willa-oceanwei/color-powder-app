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
    script = re.search(r'<script id="statement-customer-print">(.*?)</script>', html, re.S)[1]
    # Model the real top-level sheet elements, including stock wrappers.
    harness = '''
const assert=require('node:assert/strict');
const wrapped=WRAPPED;
const sheets=['RA01','RB02','RA01'].map(id=>{
  const classes=new Set();
  const customer={dataset:{customerId:id}};
  return {dataset:customer.dataset,
    matches:()=>!wrapped,querySelector:()=>customer,
    classes,classList:{remove:(...names)=>names.forEach(n=>classes.delete(n)),
      add:n=>classes.add(n),toggle:(n,on)=>on?classes.add(n):classes.delete(n)}};
});
let current=2;
const listeners={};
const printed=[];
const window={addEventListener:(name,fn)=>listeners[name]=fn,
  print:()=>printed.push(sheets.map(p=>!p.classes.has('print-omit')))};
SCRIPT
printCustomer();
assert.deepEqual(printed.pop(),[true,false,true]);
assert(sheets[2].classes.has('print-last'));
listeners.afterprint();
assert(sheets.every(p=>p.classes.size===0));
current=1;
printCustomer();
assert.deepEqual(printed.pop(),[false,true,false]);
assert(sheets[1].classes.has('print-last'));
printAll();
assert.deepEqual(printed.pop(),[true,true,true]);
assert(sheets.every(p=>p.classes.size===0));
window.print=()=>{throw new Error('cancelled')};
assert.throws(()=>printCustomer());
assert(sheets.every(p=>p.classes.size===0));
'''.replace("WRAPPED", json.dumps(stock != "standard")).replace("SCRIPT", script)
    subprocess.run([node, "-e", harness], check=True, capture_output=True, text=True)
