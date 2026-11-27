const $ = id => document.getElementById(id);
let busy = false;
async function request(data={action:'state'}) {
  const response=await fetch('/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const state=await response.json();
  if(!state.ok) throw Error(state.error || 'Request failed');
  return state;
}
function render(s){
  $('connection').textContent='● System connected';
  const received=s.rooms.reduce((a,r)=>a+r.received,0), missing=s.rooms.reduce((a,r)=>a+r.missing,0);
  $('stats').innerHTML=[['Reporting rooms',s.rooms.filter(r=>r.age!==null&&r.age<=5).length+' / 3'],['UDP readings received',received],['Sequence gaps observed',missing],['Unacknowledged alerts',s.alerts.filter(a=>!a.acknowledged&&a.status!=='Normal').length]].map(([k,v])=>`<div class="stat"><small>${k}</small><strong>${v}</strong></div>`).join('');
  // All interpolated strings come from the fixed room/scenario vocabulary in this demo.
  $('rooms').innerHTML=s.rooms.map(r=>`<article class="room"><div class="room-top"><h3>${r.name}</h3><span class="badge ${r.status}">${r.status}</span></div><div class="temperature">${r.temperature===null?'—':r.temperature.toFixed(1)}<small> °C</small></div><div class="metrics"><span>Humidity<b>${r.humidity===null?'—':r.humidity.toFixed(1)}%</b></span><span>Smoke (demo units)<b>${r.smoke===null?'—':r.smoke.toFixed(1)} / 100</b></span></div><div class="telemetry">Sequence #${r.sequence} · Received ${r.received} · Gaps ${r.missing}<br>Last reading: ${r.age===null?'waiting':r.age+'s ago'}</div><div class="controls"><label>Demo scenario<select data-room="${r.name}">${[['normal','Normal conditions'],['heat','Simulate overheating'],['smoke','Simulate smoke'],['offline','Disconnect sensor']].map(([v,t])=>`<option value="${v}" ${v===r.scenario?'selected':''}>${t}</option>`).join('')}</select></label><label><input type="checkbox" data-loss="${r.name}" ${r.drop?'checked':''}> Omit every third UDP reading</label></div></article>`).join('');
  $('alerts').innerHTML=s.alerts.length?s.alerts.map(a=>`<div class="alert"><span class="badge ${a.status}">${a.status}</span> <strong>${a.room}</strong><p>${a.reason}</p><p>${a.time}</p>${a.acknowledged?'<span class="hint">✓ Acknowledged</span>':`<button data-ack="${a.id}">Acknowledge via TCP</button>`}</div>`).join(''):'<p class="hint">All clear. Trigger a scenario to see alerts here.</p>';
  $('trace').innerHTML=s.trace.map(t=>`<div class="trace"><b>${t.protocol}</b>${t.time} · ${t.message}</div>`).join('');
}
async function act(data){busy=true;try{render(await request(data));}catch(e){$('connection').textContent=e.message;}finally{busy=false;}}
document.addEventListener('change',e=>{if(e.target.dataset.room)act({action:'scenario',room:e.target.dataset.room,scenario:e.target.value});if(e.target.dataset.loss)act({action:'drop',room:e.target.dataset.loss,enabled:e.target.checked});});
document.addEventListener('click',e=>{if(e.target.dataset.ack)act({action:'ack',id:Number(e.target.dataset.ack)});});
async function poll(){if(!busy && !['SELECT','INPUT'].includes(document.activeElement.tagName)){busy=true;try{render(await request());}catch(e){$('connection').textContent='Disconnected · check the server';}finally{busy=false;}}setTimeout(poll,1000);}
poll();
