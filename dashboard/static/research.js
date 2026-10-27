'use strict';
// Research features share the existing loaded trace and chart lifecycle.
const research = {time:0,timer:null,experiment:null,experimentRequest:null,busy:false};
function advancedConfig(){
  const config={audit_interval:Number($('audit-interval').value)};
  if($('scenario').value==='custom') config.custom_events=[...document.querySelectorAll('.custom-event')].map(row=>({
    flow:row.querySelector('.event-flow').value,start:Number(row.querySelector('.event-start').value),
    duration:Number(row.querySelector('.event-duration').value),multiplier:Number(row.querySelector('.event-multiplier').value)
  }));
  return config;
}
function flowOptions(value='f0'){
  const count=Number($('flow-count').value);
  let options=Array.from({length:count},(_,i)=>`<option value="f${i}" ${value==='f'+i?'selected':''}>F${i}</option>`).join('');
  if(!Array.from({length:count},(_,i)=>'f'+i).includes(value))options+=`<option value="${value}" selected>${value} (outside workload)</option>`;
  return options;
}
function addEventRow(){
  if(state.busy||document.querySelectorAll('.custom-event').length>=20)return;
  const row=document.createElement('div');row.className='custom-event';
  row.innerHTML=`<label>Flow<select form="config-form" class="event-flow">${flowOptions()}</select></label>
    <label>Start (s)<input form="config-form" class="event-start" type="number" value="60" min="0" max="179" step="1" required></label>
    <label>Duration (s)<input form="config-form" class="event-duration" type="number" value="25" min="1" max="180" step="1" required></label>
    <label>Rate multiplier<input form="config-form" class="event-multiplier" type="number" value="3" min="1.01" max="8" step="0.01" required></label>
    <button type="button" class="secondary remove-event" aria-label="Remove this spike">Remove</button>`;
  row.querySelector('button').addEventListener('click',()=>{if(!state.busy){row.remove();markDraft();}});
  $('custom-events').appendChild(row);markDraft();
}
function markDraft(){if(state.data)$('status').textContent='Configuration changed. Run simulation to apply; all views still use the previous loaded run.';}
function toggleBuilder(){
  const custom=$('scenario').value==='custom';$('custom-builder').hidden=!custom;
  document.querySelectorAll('#custom-events input, #custom-events select').forEach(el=>el.disabled=!custom||state.busy);
}
$('add-event').addEventListener('click',addEventRow);
$('custom-events').addEventListener('change',markDraft);
$('scenario').addEventListener('change',toggleBuilder);
$('flow-count').addEventListener('change',()=>document.querySelectorAll('.event-flow').forEach(select=>select.innerHTML=flowOptions(select.value)));
document.addEventListener('runfinished',toggleBuilder);
addEventRow();toggleBuilder();

function stopReplay(){
  clearInterval(research.timer);research.timer=null;$('replay-play').textContent='▶ Play';
}
function replayResult(side){return state.data.results.find(r=>r.name===$('replay-'+side).value);}
function replayMode(r,path,t){
  if(!r.name.includes('hybrid'))return r.name.includes('path')?'Path batch':'Individual flow';
  let mode='path';for(const c of r.transitions)if(c.path===path&&c.time<=t)mode=c.mode;
  return mode==='flow'?'Fast individual':'Path batch';
}
function cumulativeBytes(r){
  const perSecond=Array(state.data.trace.duration).fill(0);
  for(const p of r.polls)perSecond[p.time]+=64+32*p.flows.length;
  let total=0;return perSecond.map(n=>total+=n);
}
function renderReplayChart(){
  if(!state.data||state.tab!=='comparison')return;
  const cursor={id:'replayCursor',afterDatasetsDraw(chart){
    const x=chart.scales.x.getPixelForValue(research.time),ctx=chart.ctx;
    ctx.save();ctx.strokeStyle='#526a60';ctx.setLineDash([4,3]);ctx.beginPath();ctx.moveTo(x,chart.chartArea.top);ctx.lineTo(x,chart.chartArea.bottom);ctx.stroke();ctx.restore();
  }};
  replaceChart('replay-chart',{type:'line',plugins:[cursor],data:{labels:Array.from({length:180},(_,i)=>i),datasets:['left','right'].map((side,i)=>{
    const r=replayResult(side);return {label:labels[r.name],data:cumulativeBytes(r),borderColor:i?'#9871b7':'#238b6e',pointRadius:0,borderWidth:2,stepped:true};
  })},options:baseOptions('Cumulative modeled bytes')});
}
function renderReplay(){
  if(!state.data)return;
  const t=research.time,flow=$('replay-flow').value,trace=state.data.trace;
  const path=trace.flows.find(f=>f.name===flow).path;
  $('replay-clock').textContent=`${t} / 179 s`;
  $('replay-truth').textContent=`${flow.toUpperCase()} at ${t}s: actual rate ${num(trace.rates[flow][t],1)} Mb/s · ground truth ${truth(flow,t)?'ANOMALY':'healthy'} · ${path.toUpperCase()}`;
  for(const side of ['left','right']){
    const r=replayResult(side),past=r.polls.filter(p=>p.time<=t),now=past.filter(p=>p.time===t);
    const samples=past.filter(p=>p.flows.includes(flow)),last=samples.at(-1);
    const bytes=past.reduce((sum,p)=>sum+64+32*p.flows.length,0);
    const audits=(r.audits||[]).filter(a=>a.time===t);
    $('replay-'+side+'-state').innerHTML=`<h3>${labels[r.name]}</h3><span class="pill ${r.alarms[flow][t]?'alarm':''}">${r.alarms[flow][t]?'Alarm active':'Alarm clear'}</span>
      <dl class="configuration"><dt>${path.toUpperCase()} mode</dt><dd>${replayMode(r,path,t)}</dd><dt>Last flow sample</dt><dd>${last?`${last.time}s · ${num(trace.rates[flow][last.time],1)} Mb/s`:'Not sampled'}</dd>
      <dt>Polls this second</dt><dd>${now.length}</dd><dt>Cumulative polls</dt><dd>${past.length}</dd><dt>Cumulative bytes</dt><dd>${num(bytes)}</dd></dl>
      <p>${now.length?now.map(p=>p.group).join(', '):'No polls at this second.'}</p><p>${audits.length?audits.map(a=>`${a.path}: ${a.source==='reused_batch'?'audit reuses batch':'paid audit'}`).join(' · '):''}</p>`;
  }
  if(state.charts['replay-chart'])state.charts['replay-chart'].draw();
}
function initializeReplay(){
  stopReplay();research.time=0;$('replay-time').value=0;
  const choices=state.data.results.map(r=>`<option value="${r.name}">${labels[r.name]}</option>`).join('');
  $('replay-left').innerHTML=choices;$('replay-right').innerHTML=choices;
  $('replay-left').value='hybrid';$('replay-right').value='audited_hybrid';
  $('replay-flow').innerHTML=state.data.trace.flows.map(f=>`<option value="${f.name}">${f.name.toUpperCase()}</option>`).join('');
  renderReplay();renderReplayChart();
}
for(const id of ['replay-left','replay-right','replay-flow'])$(id).addEventListener('change',()=>{stopReplay();renderReplay();renderReplayChart();});
$('replay-time').addEventListener('input',()=>{stopReplay();research.time=Number($('replay-time').value);renderReplay();});
$('replay-play').addEventListener('click',()=>{
  if(!state.data)return;if(research.timer){stopReplay();return;}if(research.time===179)research.time=0;
  $('replay-play').textContent='Ⅱ Pause';research.timer=setInterval(()=>{
    research.time++;$('replay-time').value=research.time;renderReplay();if(research.time>=179)stopReplay();
  },150);
});
document.addEventListener('runstarting',stopReplay);
document.addEventListener('runloaded',initializeReplay);
document.addEventListener('tabchanged',()=>{stopReplay();if(state.tab==='comparison'&&state.data){renderReplay();renderReplayChart();}if(state.tab==='logs'&&research.experiment)renderExperiment();});
if(state.data)initializeReplay();

function renderExperiment(){
  const study=research.experiment;if(!study)return;
  $('experiment-results').hidden=false;
  const metric=$('experiment-metric').value,values=study.aggregates.map(a=>a.metrics[metric]);
  const whiskers={id:'sampleSD',afterDatasetsDraw(chart){
    const ctx=chart.ctx;ctx.save();ctx.strokeStyle='#364d43';ctx.lineWidth=1.5;
    chart.getDatasetMeta(0).data.forEach((bar,i)=>{
      const s=values[i];if(s.mean===null)return;
      const low=chart.scales.y.getPixelForValue(s.mean-s.stddev),high=chart.scales.y.getPixelForValue(s.mean+s.stddev);
      ctx.beginPath();ctx.moveTo(bar.x,low);ctx.lineTo(bar.x,high);ctx.moveTo(bar.x-5,low);ctx.lineTo(bar.x+5,low);ctx.moveTo(bar.x-5,high);ctx.lineTo(bar.x+5,high);ctx.stroke();
    });ctx.restore();
  }};
  replaceChart('experiment-chart',{type:'bar',plugins:[whiskers],data:{labels:study.aggregates.map(a=>labels[a.name]),datasets:[{label:'Seed mean ± sample SD',data:values.map(s=>s.mean),backgroundColor:colors,borderRadius:4}]},options:{responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{display:false},tooltip:{callbacks:{afterLabel:context=>{const s=values[context.dataIndex];return `SD ${num(s.stddev,3)} · ${s.defined_runs}/${study.seeds.length} defined runs`;}}}},scales:{x:{grid:{display:false},ticks:{font:{size:9}}},y:{min:Math.min(0,...values.filter(s=>s.mean!==null).map(s=>s.mean-s.stddev)),suggestedMax:Math.max(1,...values.filter(s=>s.mean!==null).map(s=>s.mean+s.stddev)),title:{display:true,text:metric.replaceAll('_',' ')}}}}});
  const cell=(a,key,d)=>`${num(a.metrics[key].mean,d)} ± ${num(a.metrics[key].stddev,d)}`;
  $('experiment-table').innerHTML=study.aggregates.map(a=>`<tr><td>${labels[a.name]}</td><td>${cell(a,'modeled_bytes',1)}</td><td>${cell(a,'f1',3)}</td><td>${cell(a,'recall',3)}</td><td>${cell(a,'mean_detection_delay_s',2)}</td><td>${a.metrics.mean_detection_delay_s.defined_runs}/${study.seeds.length}</td><td>${a.missed_events}/${a.total_events}</td></tr>`).join('');
}
$('run-experiment').addEventListener('click',async()=>{
  if(!state.data||research.busy)return;
  const raw=$('experiment-seeds').value.trim().split(',').map(s=>s.trim());
  if(raw.some(s=>!/^\d+$/.test(s))){showError(new Error('Enter comma-separated whole-number seeds.'));return;}
  const seeds=raw.map(Number),request={config:structuredClone(state.data.config),seeds};
  research.busy=true;$('run-experiment').disabled=true;$('error').hidden=true;
  $('experiment-status').textContent=`Running ${seeds.length} paired seeds on the loaded configuration…`;
  try{
    const study=await (await api('/api/experiment',request)).json();
    research.experiment=study;research.experimentRequest=request;
    $('experiment-status').textContent=`Completed ${seeds.length*study.aggregates.length} simulations · ${scenarios[study.config.scenario]} · ${study.config.flow_count} flows · audit ${study.config.audit_interval}s · seeds ${study.seeds.join(', ')}. Means ± sample SD, not confidence intervals. Custom event times stay fixed across seeds. This study stays loaded until replaced.`;
    renderExperiment();$('experiment-json').disabled=false;$('experiment-csv').disabled=false;
  }catch(error){showError(error);$('experiment-status').textContent='Experiment failed. Any previous study below is retained; its exports still refer to that study.';}
  finally{research.busy=false;$('run-experiment').disabled=false;}
});
$('experiment-metric').addEventListener('change',()=>{if(research.experiment)renderExperiment();});
for(const kind of ['json','csv'])$('experiment-'+kind).addEventListener('click',async()=>{
  if(!research.experimentRequest)return;const button=$('experiment-'+kind);button.disabled=true;
  try{
    const response=await api('/api/experiment/export/'+kind,research.experimentRequest);
    const url=URL.createObjectURL(await response.blob()),a=document.createElement('a');a.href=url;a.download='flowscope-experiment.'+kind;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(error){showError(error);}finally{button.disabled=false;}
});
