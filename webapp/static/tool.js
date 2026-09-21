const id=location.pathname.split('/').filter(Boolean).pop();
const $=s=>document.querySelector(s);let job=null,ws=null;
const meta={
 wo_unified:['📦','WO Extractor','Extract GPON / Fiber work-order PDFs into Excel','The uploaded PDFs are sent to the real WO parsing engine.'],
 db:['▥','DB Automation','Validate, update or add records through Selenium','Uses DB/core/processor.py and the real service modules.'],
 ftth_portal:['◎','FTTH Portal','Extract KAM Order data from the FTTH portal','Uses the real Selenium portal flow. CAPTCHA is entered in this page.'],
 psc:['⌁','PSC Extractor','Extract ESC/P request data from Excel IDs','Uses the real Playwright extraction engine.']
};
const m=meta[id]||['⚡','Automation Tool','',''];$('#icon').textContent=m[0];$('#title').textContent=m[1];$('#desc').textContent=m[2];$('#notice').textContent=m[3];
function field(label,name,type='text',full=false){const d=document.createElement('div');d.className='field '+(full?'full':'');d.innerHTML=`<label>${label}</label>`;const x=document.createElement(type==='textarea'?'textarea':'input');x.name=name;x.type=type;if(type==='file'){x.accept=id==='wo_unified'?'.pdf':'.xlsx,.xls';x.multiple=id==='wo_unified'}d.appendChild(x);$('#fields').appendChild(d);return x}
function select(label,name,opts){const d=document.createElement('div');d.className='field';d.innerHTML=`<label>${label}</label><select name="${name}">${opts.map(x=>`<option value="${x}">${x}</option>`).join('')}</select>`;$('#fields').appendChild(d)}
if(id==='wo_unified'){field('PDF files','files','file');select('Technology','mode',['GPON','Fiber'])}
if(id==='db'){field('Excel input','file','file');select('Action','action',['validate','update','add']);select('Service type','service_type',['fiber','ftth','wimax','shdsl','vdsl']);field('Username','username');field('Password','password');field('Fields (comma separated)','selected_fields','text',true)}
if(id==='ftth_portal'){field('Excel input','file','file');field('Username','username');field('Password','password')}
if(id==='psc'){field('Excel input','file','file');field('Username','username');field('Password','password');field('Domain','domain')}
async function prefill(){if(!['db','ftth_portal','psc'].includes(id))return;try{const c=await fetch('/api/webtools/'+id+'/credentials').then(r=>r.json());const u=document.querySelector('[name=username]');if(u&&!u.value)u.value=c.username||'';const d=document.querySelector('[name=domain]');if(d&&!d.value)d.value=c.domain||'CAIRO.TELECOMEGYPT.CORP';}catch{}}
prefill();
function logLine(x){const box=$('#logs');box.textContent+=(box.textContent?'\n':'')+x;box.scrollTop=box.scrollHeight}
function showJob(d){job=d.job_id;$('#jobCard').classList.remove('hidden');$('#jobTitle').textContent=`${m[1]} · ${job}`;$('#jobMeta').textContent='Running real backend engine…';$('#logs').textContent='Job accepted…';connect();poll()}
function connect(){if(ws)try{ws.close()}catch{}const proto=location.protocol==='https:'?'wss':'ws';ws=new WebSocket(`${proto}://${location.host}/ws/logs/${job}`);ws.onmessage=e=>{const d=JSON.parse(e.data);if(d.type==='log')logLine(`[${d.timestamp}] ${d.message}`);if(d.type==='progress'&&d.value!=null)$('#bar').style.width=d.value+'%';if(d.type==='captcha'){ $('#captchaBox').classList.remove('hidden');$('#captchaImg').src=d.image_url+'&_='+Date.now();$('#captchaInput').focus();}if(d.type==='status'){setStatus(d.status);if(d.output_file)showDownload()}}}
function setStatus(s){$('#status').textContent=String(s||'running').toUpperCase();if(s==='done')$('#bar').style.width='100%'}
function showDownload(){const a=$('#download');a.href='/api/jobs/'+job+'/download';a.classList.remove('hidden')}
async function poll(){if(!job)return;try{const d=await fetch('/api/jobs/'+job).then(r=>r.json());setStatus(d.status);$('#bar').style.width=(d.progress||((d.status==='done')?100:0))+'%';if(d.output_file)showDownload();if(['done','error','stopped'].includes(d.status))return;setTimeout(poll,1200)}catch{setTimeout(poll,1800)}}
$('#form').onsubmit=async e=>{e.preventDefault();const fd=new FormData($('#form'));if(id==='wo_unified'){if(!fd.getAll('files').some(f=>f.name)){alert('Please select at least one PDF.');return}}else{const f=fd.get('file');if(!f||!f.name){alert('Please select an Excel file.');return}}try{const r=await fetch('/api/webtools/'+id+'/run',{method:'POST',body:fd});const d=await r.json();if(!r.ok)throw Error(d.detail||'Failed to start');showJob(d)}catch(e){alert(e.message)}};
$('#stop').onclick=async()=>{if(job)await fetch('/api/jobs/'+job+'/stop',{method:'POST'});};
$('#captchaBtn').onclick=async()=>{const v=$('#captchaInput').value.trim();if(!v)return;try{await fetch('/api/jobs/'+job+'/captcha',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({captcha:v})});$('#captchaBox').classList.add('hidden');}catch(e){alert('Unable to submit CAPTCHA')}};
