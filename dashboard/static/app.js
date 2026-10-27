'use strict';
const $ = id => document.getElementById(id);
const labels = {fixed:'Fixed flow',fixed_path:'Fixed path batch',flow_adaptive:'Adaptive flow',path_adaptive:'Adaptive path',hybrid:'Hybrid path-to-flow'};
const scenarios = {single:'Single-flow spike',simultaneous:'Simultaneous spikes',offsetting:'Offsetting changes'};
const colors = ['#8a9b9a','#697aae','#c79158','#379b87','#174b40'];
const state = {data:null,tab:'topology',path:'p0',time:0,flow:'f0',page:0,timer:null,charts:{},busy:false};
const num = (v,d=0) => v === null || v === undefined ? 'N/A' : Number(v).toLocaleString('en-US',{maximumFractionDigits:d,minimumFractionDigits:d});
const result = () => state.data.results.find(r=>r.name===state.data.config.policy);
const truth = (flow,t) => state.data.trace.events.some(e=>e.flow===flow&&e.start<=t&&t<e.end);
const members = path => state.data.trace.flows.filter(f=>f.path===path);
function modeAt(path,t){
  if(state.data.config.policy!=='hybrid') return state.data.config.policy.includes('path')?'Path batch':'Individual flow';
  let mode='path';
  for(const change of result().transitions) if(change.path===path&&change.time<=t) mode=change.mode;
  return mode==='path'?'Path batch':'Fast individual';
}
function showError(error){$('error').hidden=false;$('error').textContent=error.message||String(error);}
function pause(){if(state.timer)clearInterval(state.timer);state.timer=null;$('play').textContent='▶';$('play').setAttribute('aria-label','Play trace replay');}
async function api(url,config){
  const response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(config)});
  if(!response.ok){let message;try{message=(await response.json()).error;}catch{message=`Request failed (${response.status})`;}
    throw new Error(message);}
  return response;
}
function currentConfig(){return {policy:$('policy').value,scenario:$('scenario').value,seed:Number($('seed').value),flow_count:Number($('flow-count').value)};}
async function runSimulation(event){
  if(event)event.preventDefault();
  if(state.busy||!$('config-form').reportValidity())return;
  const config=currentConfig();state.busy=true;pause();$('error').hidden=true;
  $('run-button').textContent='Running…';$('status').textContent='Computing all five policies on one shared traffic trace…';
  $('run-state').textContent='Running';
  [...$('config-form').elements].forEach(e=>e.disabled=true);
  try{
    state.data=await (await api('/api/run',config)).json();
    state.time=0;state.path='p0';state.flow='f0';state.page=0;$('time').value=0;
    $('run-state').textContent='Run complete';$('run-id').textContent='#'+state.data.run_id;
    $('status').textContent=`Loaded: ${labels[config.policy]} · ${scenarios[config.scenario]} · seed ${config.seed} · ${config.flow_count} flows. All five policies use this trace.`;
    const options=state.data.trace.flows.map(f=>`<option value="${f.name}">${f.name.toUpperCase()} · ${f.path.toUpperCase()}</option>`).join('');
    $('inspect-flow').innerHTML=options;$('log-flow').innerHTML='<option value="all">All flows</option>'+options;
    renderMetrics();renderTopology();renderActive();
    document.querySelectorAll('[data-export]').forEach(b=>b.disabled=false);
  }catch(error){showError(error);$('status').textContent=state.data?'Run failed. The previous loaded results remain on screen.':'Run failed. Check the local server and try again.';$('run-state').textContent='Run failed';}
  finally{state.busy=false;$('run-button').innerHTML='<span>▶</span> Run simulation';[...$('config-form').elements].forEach(e=>e.disabled=false);}
}
function renderMetrics(){
  const m=result().metrics;
  const items=[['Monitoring overhead',num(m.modeled_bytes),'B',`${num(m.messages)} request + response messages`],
    ['Poll transactions',num(m.poll_transactions),'',`${num(m.records)} returned flow records`],
    ['Detection F1',num(m.f1,3),'',`Recall ${m.recall===null?'N/A':num(m.recall*100,1)+'%'}`],
    ['Mean detection delay',num(m.mean_detection_delay_s,1),'s',`${m.detected_events} / ${m.total_events} events detected`]];
  $('metrics').innerHTML=items.map(([label,value,unit,foot],i)=>`<article class="metric"><div class="metric-label">${label}<span>0${i+1}</span></div><div class="metric-value">${value}<small>${unit}</small></div><div class="metric-foot">${foot}</div></article>`).join('');
}
const points={s0:[105,185],s1:[365,92],s2:[365,282],s3:[680,185]};
function flowPoint(path,index,count){
  const route=state.data.trace.paths[path].map(s=>points[s]);
  const u=(index+.5)/count*2;
  const segment=Math.min(1,Math.floor(u)),fraction=.14+.72*(u-segment);
  return [route[segment][0]+(route[segment+1][0]-route[segment][0])*fraction,route[segment][1]+(route[segment+1][1]-route[segment][1])*fraction];
}
function renderTopology(){
  if(!state.data)return;
  const {trace}=state.data,t=state.time,r=result();
  $('stage-time').textContent=`t = ${String(t).padStart(3,'0')} s`;
  $('time-label').textContent=`${String(t).padStart(3,'0')} / ${trace.duration-1} s`;
  $('topology-count').textContent=`4 switches · ${trace.flows.length} flows`;
  let markup='<defs><filter id="glow"><feGaussianBlur stdDeviation="3"/></filter></defs>';
  for(const [path,route] of Object.entries(trace.paths)){
    const selected=path===state.path,active=members(path).some(f=>truth(f.name,t));
    const stroke=selected?'#79dbb5':active?'#b5784b':'#365e56';
    const coords=route.map(s=>points[s].join(',')).join(' ');
    markup+=`<g class="network-link" data-path="${path}" tabindex="0" role="button" aria-label="Inspect ${path}" opacity="${selected?1:.7}"><polyline points="${coords}" fill="none" stroke="transparent" stroke-width="24"/><polyline points="${coords}" fill="none" stroke="${stroke}" stroke-width="${selected?3:2}" ${selected?'':'stroke-dasharray="5 6"'}/></g>`;
  }
  for(const [node,[x,y]] of Object.entries(points)){
    const onPath=trace.paths[state.path].includes(node);
    markup+=`<g class="svg-hit" data-node="${node}" tabindex="0" role="button" aria-label="Inspect switch ${node}"><rect class="node-box" x="${x-34}" y="${y-24}" width="68" height="48" rx="9" fill="${onPath?'#244b42':'#1d3b38'}" stroke="${onPath?'#72b99a':'#42645b'}"/><path d="M${x-16} ${y-5} h32 M${x-16} ${y+1} h32" stroke="#8ab4a2" stroke-width="2"/>${[-12,-4,4,12].map(dx=>`<rect x="${x+dx-2}" y="${y+8}" width="4" height="3" fill="#89d0ac"/>`).join('')}<text x="${x}" y="${y+45}" text-anchor="middle" fill="#cee8db" font-size="12" font-family="Consolas,monospace">${node.toUpperCase()}</text><text x="${x}" y="${y+59}" text-anchor="middle" fill="#6f9986" font-size="8">${node==='s0'?'INGRESS':node==='s3'?'EGRESS':'CORE SWITCH'}</text></g>`;
  }
  const group=members(state.path);
  group.forEach((flow,i)=>{
    const [x,y]=flowPoint(state.path,i,group.length),active=truth(flow.name,t),alarm=r.alarms[flow.name][t];
    markup+=`<g data-flow="${flow.name}" class="svg-hit" tabindex="0" role="button" aria-label="Inspect flow ${flow.name}"><circle cx="${x}" cy="${y}" r="${alarm?10:7}" fill="${alarm?'#bba2da':'#183c32'}"/><circle cx="${x}" cy="${y}" r="6" fill="${active?'#e9a064':'#80ddba'}" stroke="#18352e" stroke-width="2"/><text x="${x}" y="${y-14}" text-anchor="middle" fill="#b5d6c4" font-size="9" font-family="Consolas,monospace">${flow.name}</text></g>`;
  });
  $('network').innerHTML=markup;
  $('path-tabs').innerHTML=Object.entries(trace.paths).map(([p,route])=>`<button type="button" class="path-button ${p===state.path?'active':''}" data-path="${p}">${p.toUpperCase()} · ${modeAt(p,t)}<span>${route.join(' → ')}</span></button>`).join('');
  $('path-title').textContent=`Path ${state.path.slice(1).padStart(2,'0')}`;
  $('path-mode').textContent=modeAt(state.path,t);$('path-mode').className='pill'+(modeAt(state.path,t)==='Fast individual'?' alarm':'');
  $('path-route').textContent=trace.paths[state.path].map(s=>s.toUpperCase()).join(' → ');
  $('path-rate').textContent=num(group.reduce((s,f)=>s+trace.rates[f.name][t],0),1);
  $('path-detail').textContent=`${group.length} flows · ${group.filter(f=>truth(f.name,t)).length} anomalies · ${group.filter(f=>r.alarms[f.name][t]).length} held alarms`;
  $('path-flows').innerHTML=group.map(f=>`<div class="flow-mini"><code>${f.name.toUpperCase()}</code><span>${num(trace.rates[f.name][t],1)} Mb/s</span><span class="pill ${truth(f.name,t)?'alert':''}">${truth(f.name,t)?'Anomaly':'Healthy'}</span></div>`).join('');
  $('flow-table').innerHTML=trace.flows.map(f=>{
    const samples=r.polls.filter(p=>p.time<=t&&p.flows.includes(f.name));
    const last=samples.length?samples[samples.length-1].time:null;
    return `<tr class="${f.path===state.path?'selected-row':''}"><td><code>${f.name.toUpperCase()}</code></td><td>${f.path.toUpperCase()}</td><td>${num(f.reference)} Mb/s</td><td>${num(trace.rates[f.name][t],1)} Mb/s</td><td><span class="pill ${truth(f.name,t)?'alert':''}">${truth(f.name,t)?'Anomaly':'Healthy'}</span></td><td><span class="pill ${r.alarms[f.name][t]?'alarm':''}">${r.alarms[f.name][t]?'Active':'Clear'}</span></td><td>${last===null?'Not sampled':last+' s'}</td></tr>`;
  }).join('');
}
function replaceChart(id,config){
  state.charts[id]?.destroy();
  state.charts[id]=new Chart($(id),config);
}
function baseOptions(yLabel){
  return {
    responsive:true,maintainAspectRatio:false,animation:false,
    interaction:{mode:'index',intersect:false},
    plugins:{legend:{position:'bottom',labels:{boxWidth:10,boxHeight:10,usePointStyle:true,padding:18,font:{size:10}}}},
    scales:{
      x:{grid:{display:false},ticks:{maxTicksLimit:7,font:{size:10}},title:{display:true,text:'Time (seconds)',font:{size:10}}},
      y:{beginAtZero:true,grid:{color:'#edf1ee'},ticks:{font:{size:10}},title:{display:true,text:yLabel,font:{size:10}}}
    }
  };
}
function renderSimulation(){
  if(!state.data)return;
  const trace=state.data.trace,r=result(),flow=state.flow;
  const times=Array.from({length:trace.duration},(_,i)=>i),reference=trace.flows.find(f=>f.name===flow).reference;
  const sampled=new Set(r.polls.filter(p=>p.flows.includes(flow)).map(p=>p.time));
  const path=trace.flows.find(f=>f.name===flow).path;
  $('traffic-title').textContent=`${flow.toUpperCase()} · traffic and sampled rates`;
  const changeLines={id:'modeChanges',afterDatasetsDraw(chart){
    const {ctx,chartArea,scales}=chart;ctx.save();ctx.strokeStyle='#aa91c7';ctx.setLineDash([3,4]);
    for(const change of r.transitions.filter(c=>c.path===path)){
      const x=scales.x.getPixelForValue(change.time);ctx.beginPath();ctx.moveTo(x,chartArea.top);ctx.lineTo(x,chartArea.bottom);ctx.stroke();
    }ctx.restore();
  }};
  replaceChart('traffic-chart',{type:'line',plugins:[changeLines],data:{labels:times,datasets:[
    {label:'Actual rate (Mb/s)',data:trace.rates[flow],borderColor:'#278b70',backgroundColor:'#278b7010',fill:true,pointRadius:0,borderWidth:2},
    {label:'Alarm threshold',data:times.map(()=>reference*state.data.settings.alarm_multiplier),borderColor:'#c99965',borderDash:[5,5],pointRadius:0,borderWidth:1},
    {label:'Polled sample',data:times.map(t=>sampled.has(t)?trace.rates[flow][t]:null),showLine:false,pointRadius:3,pointBackgroundColor:'#8061a8',borderColor:'#8061a8'}]},options:baseOptions('Mb/s')});
  replaceChart('alarm-chart',{type:'line',data:{labels:times,datasets:[
    {label:'Ground-truth anomaly',data:times.map(t=>Number(truth(flow,t))),borderColor:'#d58c4e',backgroundColor:'#d58c4e20',fill:true,pointRadius:0,stepped:true,borderWidth:2},
    {label:'Held monitor alarm',data:r.alarms[flow].map(Number),borderColor:'#8867b0',pointRadius:0,stepped:true,borderWidth:2,borderDash:[5,3]}]},options:{...baseOptions('Alarm state'),scales:{...baseOptions('').scales,y:{min:0,max:1.1,ticks:{stepSize:1,callback:v=>v===1?'Active':v===0?'Clear':''},grid:{color:'#edf1ee'}}}}});
  const polls=times.map(t=>r.polls.filter(p=>p.time===t));
  replaceChart('poll-chart',{type:'bar',data:{labels:times,datasets:[
    {label:'Transactions',data:polls.map(ps=>ps.length),backgroundColor:'#31967b'},
    {label:'Returned records',data:polls.map(ps=>ps.reduce((s,p)=>s+p.flows.length,0)),backgroundColor:'#a3cdbb'}]},options:baseOptions('Count / second')});
  if(state.data.config.policy!=='hybrid'){
    $('mode-timeline').innerHTML='<p class="mode-caption">This policy does not switch between path and flow modes. Its polling activity is shown above.</p>';return;
  }
  $('mode-timeline').innerHTML=Object.keys(trace.paths).map(p=>{
    const changes=[{time:0,mode:'path'},...r.transitions.filter(c=>c.path===p),{time:trace.duration,mode:'end'}];
    return `<div class="mode-row"><code>${p.toUpperCase()}</code><div class="mode-track">${changes.slice(0,-1).map((c,i)=>`<div class="mode-segment ${c.mode==='flow'?'fast':''}" style="width:${(changes[i+1].time-c.time)/trace.duration*100}%" title="${p}: ${c.mode} mode, ${c.time}–${changes[i+1].time} s"></div>`).join('')}</div></div>`;
  }).join('')+`<p class="mode-caption">Green: path batches · Purple: fast individual polls · Dashed vertical traffic-chart lines: mode switches on ${path.toUpperCase()}.</p>`+
    `<p class="mode-caption">${r.transitions.length?r.transitions.map(c=>`${c.path.toUpperCase()} → ${c.mode} at ${c.time}s`).join(' · '):'No mode switches in this run. Aggregate changes never triggered flow mode.'}</p>`;
}
function comparisonChart(id,metric){
  const ratios=['f1','recall'].includes(metric);
  replaceChart(id,{
    type:'bar',
    data:{labels:state.data.results.map(r=>labels[r.name].replace(' path-to-flow','')),
      datasets:[{label:metric.replaceAll('_',' '),data:state.data.results.map(r=>r.metrics[metric]),backgroundColor:colors,borderRadius:4,maxBarThickness:48}]},
    options:{responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{display:false}},
      scales:{
        x:{grid:{display:false},ticks:{font:{size:9},maxRotation:20}},
        y:{beginAtZero:true,...(ratios?{max:1}:{}),grid:{color:'#edf1ee'},title:{display:true,text:metric.replaceAll('_',' '),font:{size:10}},ticks:{font:{size:10}}}
      }
    }
  });
}
function renderComparison(){
  $('comparison-config').textContent=`Seed ${state.data.config.seed} · ${state.data.config.flow_count} flows`;
  comparisonChart('cost-chart',$('cost-metric').value);comparisonChart('quality-chart',$('quality-metric').value);
  $('comparison-table').innerHTML=state.data.results.map(r=>`<tr class="${r.name===state.data.config.policy?'selected-row':''}"><td>${labels[r.name]}</td><td>${num(r.metrics.modeled_bytes)}</td><td>${num(r.metrics.poll_transactions)}</td><td>${num(r.metrics.records)}</td><td>${num(r.metrics.recall,3)}</td><td>${num(r.metrics.f1,3)}</td><td>${num(r.metrics.mean_detection_delay_s,1)} s</td><td>${r.metrics.detected_events} / ${r.metrics.total_events}</td></tr>`).join('');
  const hybrid=state.data.results.find(r=>r.name==='hybrid').metrics,path=state.data.results.find(r=>r.name==='path_adaptive').metrics;
  const delta=hybrid.modeled_bytes-path.modeled_bytes;
  $('comparison-insight').textContent=`Hybrid vs adaptive path in this trace: ${delta===0?'equal modeled bytes':num(Math.abs(delta))+' '+(delta>0?'more':'fewer')+' modeled bytes'}. F1: ${num(hybrid.f1,3)} vs ${num(path.f1,3)}. Initial mean delay: ${num(hybrid.mean_detection_delay_s,1)} s vs ${num(path.mean_detection_delay_s,1)} s. This is a single-seed result, not a general ranking.`;
}
function renderLogs(){
  const c=state.data.config,s=state.data.settings,r=result();
  const configRows=[['Run ID',state.data.run_id],['Scenario',scenarios[c.scenario]],['Selected policy',labels[c.policy]],['Seed',c.seed],['Workload',c.flow_count+' flows'],['Duration','180 seconds'],['Fixed / minimum / maximum',`${s.fixed_interval} / ${s.minimum} / ${s.maximum} s`],['Change threshold',num(s.change_threshold*100)+'%'],['Alarm threshold',s.alarm_multiplier+' × reference'],['Hybrid stable rounds','2'],['Additional flows',c.flow_count>6?'Healthy background':'None']];
  $('configuration').innerHTML=configRows.map(([k,v])=>`<dt>${k}</dt><dd>${v}</dd>`).join('');
  $('event-outcomes').innerHTML=r.events.map(e=>`<div class="event-outcome"><div><strong>${e.flow.toUpperCase()}</strong><small>Ground truth: [${e.start}, ${e.end}) s</small></div><div><span class="pill ${e.delay_s===null?'alert':''}">${e.delay_s===null?'Missed':e.delay_s+' s delay'}</span><small>${e.delay_s===null?'No positive in-event sample':'Detected at '+(e.start+e.delay_s)+' s'}</small></div></div>`).join('');
  renderPollLog();
}
function renderPollLog(){
  if(!state.data)return;
  const filter=$('log-flow').value;
  const rows=result().polls.filter(p=>filter==='all'||p.flows.includes(filter));
  const size=15,start=state.page*size,visible=rows.slice(start,start+size);
  $('poll-log').innerHTML=visible.map(p=>`<tr><td><code>${String(p.time).padStart(3,'0')} s</code></td><td><code>${p.group}</code></td><td>${p.flows.join(', ')}</td><td>${p.flows.length}</td><td>2</td><td>${64+32*p.flows.length}</td></tr>`).join('');
  $('log-count').textContent=rows.length?`${start+1}–${Math.min(start+size,rows.length)} of ${rows.length} transactions`:'No transactions';
  $('prev-page').disabled=state.page===0;$('next-page').disabled=start+size>=rows.length;
}
const titles={topology:['A clear view of your network.','Follow traffic, inspect paths, and see how monitoring adapts.'],simulation:['Watch the policy at work.','Separate the traffic that happened from what the monitor observed.'],comparison:['Measure the trade-offs.','Compare collection cost and detection quality on identical traffic.'],logs:['Every result has a trail.','Inspect configurations, event outcomes, and the complete polling record.']};
function renderActive(){if(!state.data)return;if(state.tab==='simulation')renderSimulation();if(state.tab==='comparison')renderComparison();if(state.tab==='logs')renderLogs();}
function switchTab(tab){
  pause();state.tab=tab;
  document.querySelectorAll('.tab-panel').forEach(p=>p.hidden=p.id!=='tab-'+tab);
  document.querySelectorAll('[data-tab]').forEach(b=>{b.classList.toggle('active',b.dataset.tab===tab);if(b.dataset.tab===tab)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
  $('breadcrumb').textContent=tab==='logs'?'Experiments & Logs':tab[0].toUpperCase()+tab.slice(1);
  $('page-title').textContent=titles[tab][0];$('page-subtitle').textContent=titles[tab][1];renderActive();
}
document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>switchTab(b.dataset.tab)));
$('config-form').addEventListener('submit',runSimulation);
$('config-form').addEventListener('change',()=>{if(state.data)$('status').textContent='Configuration changed. Press Run simulation to apply; the views still show the previous loaded run.';});
$('time').addEventListener('input',()=>{pause();state.time=Number($('time').value);renderTopology();});
$('play').addEventListener('click',()=>{
  if(!state.data)return;if(state.timer){pause();return;}if(state.time>=179)state.time=0;
  $('play').textContent='Ⅱ';$('play').setAttribute('aria-label','Pause trace replay');
  state.timer=setInterval(()=>{state.time++;$('time').value=state.time;renderTopology();if(state.time>=179)pause();},150);
});
function inspect(event){
  if(!state.data)return;
  const target=event.target.closest('[data-path],[data-node],[data-flow]');if(!target)return;
  if(target.dataset.path){state.path=target.dataset.path;$('selection-note').textContent='Selected '+state.path.toUpperCase()+'. Rate and alarms reflect the replay time.';}
  if(target.dataset.node){const paths=Object.keys(state.data.trace.paths).filter(p=>state.data.trace.paths[p].includes(target.dataset.node));$('selection-note').textContent=`Switch ${target.dataset.node.toUpperCase()} participates in ${paths.map(p=>p.toUpperCase()).join(', ')}. Routes are fixed in this model.`;state.path=paths.includes(state.path)?state.path:paths[0];}
  if(target.dataset.flow){state.flow=target.dataset.flow;$('inspect-flow').value=state.flow;$('selection-note').textContent=`Flow ${state.flow.toUpperCase()} selected for the Simulation tab. Use the replay slider to inspect its state.`;}
  renderTopology();
}
$('network').addEventListener('click',inspect);$('path-tabs').addEventListener('click',inspect);
$('network').addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();inspect(e);}});
$('inspect-flow').addEventListener('change',()=>{state.flow=$('inspect-flow').value;renderSimulation();});
$('cost-metric').addEventListener('change',()=>{if(state.data)comparisonChart('cost-chart',$('cost-metric').value);});
$('quality-metric').addEventListener('change',()=>{if(state.data)comparisonChart('quality-chart',$('quality-metric').value);});
$('log-flow').addEventListener('change',()=>{state.page=0;renderPollLog();});
$('prev-page').addEventListener('click',()=>{if(state.page>0){state.page--;renderPollLog();}});
$('next-page').addEventListener('click',()=>{state.page++;renderPollLog();});
document.querySelectorAll('[data-export]').forEach(button=>{button.disabled=true;button.addEventListener('click',async()=>{
  if(!state.data)return;button.disabled=true;$('error').hidden=true;
  const config={...state.data.config},id=state.data.run_id,kind=button.dataset.export;
  try{const response=await api('/api/export/'+kind,config),blob=await response.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');
    a.href=url;a.download=`sdn-${id}-${kind}.${kind==='json'?'json':'csv'}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(error){showError(error);}finally{button.disabled=false;}
});});
async function init(){
  try{
    if(typeof Chart==='undefined')throw new Error('Chart.js failed to load. Check that the local vendor file is present.');
    Chart.defaults.font.family="'Segoe UI', Arial, sans-serif";Chart.defaults.color='#7b8b82';
    const response=await fetch('/api/meta');if(!response.ok)throw new Error('Cannot connect to the local engine.');
    const meta=await response.json();$('flow-count').innerHTML=meta.flow_counts.map(n=>`<option value="${n}">${n} flows${n===6?' · original':' · expanded'}</option>`).join('');
    await runSimulation();
  }catch(error){showError(error);$('status').textContent='Dashboard startup failed. Start the Flask server and reload.';}
}
init();
