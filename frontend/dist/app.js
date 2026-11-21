(function(){
'use strict';
const {UI,esc,icon,$,cap,time,fmt,active,locks,stale,sev,href,markupMedia,signal,band,peek,sortFeeds,kpis,show,bindMedia,feedCard}=A;
const dialog=$('#dialog'),modal=$('#modal');let toastTimer,modalCleanup=()=>{},metricTimer,calPoints=[],pendingCal=null,audioTimer,channel;
const unique=()=>crypto.randomUUID();
function toast(message){$('#toast').textContent=message;$('#toast').classList.add('on');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').classList.remove('on'),3800);}
function open(title,body,cleanup=()=>{}){modalCleanup();modalCleanup=cleanup;modal.innerHTML=`<div class="modal-head"><h2 id="modal-title">${esc(title)}</h2><button class="icon-btn" data-action="close" aria-label="Close dialog">${icon('cross')}</button></div>${body}`;dialog.setAttribute('aria-labelledby','modal-title');if(!dialog.open)dialog.showModal();bindMedia();}
dialog.addEventListener('close',()=>{modalCleanup();modalCleanup=()=>{};});
dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});
const field=(label,html)=>`<label class="field"><span>${label}</span>${html}</label>`;
const footer=(submit)=>`<div class="form-error" role="alert"></div><div class="form-footer"><button type="button" data-action="close">Cancel</button><button class="primary" type="submit">${esc(submit)}</button></div>`;
const freshId=id=>encodeURIComponent(id);
function eventLog(feed_id,severity,title,message,category='system',event_id=unique()){UI.events.set(event_id,{event_id,feed_id,severity,title,message,category,timestamp:new Date().toISOString()});}
function snapshot(s){
 UI.feeds=new Map((s.feeds||[]).filter(x=>x.feed_id).map(f=>[String(f.feed_id),{...f,feed_id:String(f.feed_id)}]));
 UI.incidents=new Map((s.incidents||s.active_incidents||[]).filter(i=>i.incident_id&&i.state==='active').map(i=>[i.incident_id,i]));
 UI.events=new Map((s.events||s.alerts||[]).filter(e=>e.event_id).map(e=>[e.event_id,e]));
 if(Number.isFinite(s.stale_timeout_seconds)&&s.stale_timeout_seconds>0)UI.staleAfter=s.stale_timeout_seconds;
}
function freeMedia(id){const f=UI.feeds.get(id);UI.streams.get(id)?.getTracks().forEach(t=>t.stop());UI.streams.delete(id);if(UI.objectUrls.delete(f?.preview_url))URL.revokeObjectURL(f.preview_url);}
function switchData(){UI.adapter?.stop();UI.adapter=null;UI.feeds.forEach(f=>freeMedia(f.feed_id));UI.feeds.clear();UI.incidents.clear();UI.events.clear();}
function setStatus(s){UI.status=s;$('#connection').hidden = !s;
    $('#connection').innerHTML='<b></b>'+esc(s);$('#connection').classList.toggle('off',['Disconnected','Connecting'].includes(s));}
async function startDemo(){switchData();UI.mode='demo';setStatus("");snapshot(EntropyData.demoSnapshot());let rec=null;try{rec=await EntropyData.demoRecord(false);}catch{}if(rec&&UI.mode==='demo')applyDemoRecord(rec);show();}
function applyDemoRecord(rec){
 const f=UI.feeds.get('gate');if(!f)return;
 if(rec.resolved){UI.incidents.delete('sample-gate');Object.assign(f,{severity:'normal',risk_score:18,people_count:58,density_people_per_m2:58/f.zone_area_m2,density_trend:'falling',growth_rate:-.12,metric_timestamp:rec.when});}
 else{UI.incidents.set('sample-gate',{incident_id:'sample-gate',feed_id:'gate',state:'active',acknowledged:!!rec.acknowledged});Object.assign(f,{severity:'critical',risk_score:98,people_count:186,density_people_per_m2:186/f.zone_area_m2,density_trend:'rising',growth_rate:.14});}
 if(rec.when){const title=rec.resolved?'Recovery confirmed':rec.acknowledged?'Incident acknowledged':'Critical incident opened';UI.events.set('sample-state-'+rec.when,{event_id:'sample-state-'+rec.when,feed_id:'gate',severity:rec.resolved?'normal':'critical',category:'crowd',title,message:rec.resolved?'The sample backend confirmed recovery.':rec.acknowledged?'Operator acknowledged the warning. Monitoring continues.':'The configured density limit was crossed.',timestamp:rec.when});}
}
async function saveDemoState(rec){rec.when=new Date().toISOString();await EntropyData.demoRecord(true,rec);applyDemoRecord(rec);channel?.postMessage(rec);}
function guarded(target){return locks().length>0&&target!=='events'&&!(target.startsWith('feed/')&&active().some(i=>i.feed_id===target.slice(5)));}
function guard(){open('Critical zone needs attention',`<p class="subtle">Acknowledge each active critical warning before switching workspaces.</p><div class="form" style="margin-top:16px">${locks().map(i=>`<div class="split"><a class="btn" href="${href(i.feed_id)}">${icon('cam')} ${esc(UI.feeds.get(i.feed_id)?.name||i.feed_id)}</a><button class="ack" data-ack="${esc(i.incident_id)}">Acknowledge</button></div>`).join('')}</div>`);}
function readRoute(){let r;try{r=decodeURIComponent(location.hash.slice(1))||'overview';}catch{r='overview';}return ['overview','events','diagnostics'].includes(r)||r.startsWith('feed/')?r:'overview';}
function navigate(){let r=readRoute();if(r!==UI.route&&guarded(r)){history.replaceState(null,'','#'+encodeURI(UI.route));guard();return;}
 if(dialog.open)dialog.close();UI.route=r;show();window.scrollTo(0,0);}
async function ack(id){const i=UI.incidents.get(id);if(!i||i.acknowledged)return;
 if(UI.mode==='demo'){await saveDemoState({acknowledged:true,resolved:false});}
 else{const result=await UI.adapter.call(`/api/incidents/${freshId(id)}/acknowledge/`,'POST',{});if(!(result.acknowledged||result.incident?.acknowledged)){toast('Acknowledgement sent. Waiting for server confirmation.');return;}const latest=UI.incidents.get(id);if(latest)UI.incidents.set(id,{...latest,...result.incident,acknowledged:true});}
 if(dialog.open){if(locks().length)guard();else dialog.close();}show();toast('Warning acknowledged. The zone remains pinned.');}
function beep(){if(!UI.audio||!locks().length)return;const ctx=UI.audio;if(ctx.state!=='running')return;const osc=ctx.createOscillator(),gain=ctx.createGain();osc.frequency.value=620;gain.gain.setValueAtTime(.0001,ctx.currentTime);gain.gain.exponentialRampToValueAtTime(.045,ctx.currentTime+.02);gain.gain.exponentialRampToValueAtTime(.0001,ctx.currentTime+.23);osc.connect(gain);gain.connect(ctx.destination);osc.start();osc.stop(ctx.currentTime+.25);}
async function audioToggle(){if(UI.audio){clearInterval(audioTimer);await UI.audio.close();UI.audio=null;}else{UI.audio=new AudioContext();await UI.audio.resume();beep();audioTimer=setInterval(beep,6000);}
 $('#audio').innerHTML=icon(UI.audio?'sound':'muted');const t=UI.audio?'Mute incident sound':'Enable incident sound';$('#audio').title=t;$('#audio').setAttribute('aria-label',t);toast(UI.audio?'Incident sound enabled.':'Incident sound muted.');}
function addDialog(){
 let stream=null,inFlight=0;const stop=()=>{inFlight++;stream?.getTracks().forEach(t=>t.stop());stream=null;};
 open('Add camera feed',`<form class="form" id="source-form">${field('Feed name','<input name="name" placeholder="e.g. South Gate" required maxlength="70">')}${field('Zone or location','<input name="location" placeholder="e.g. South entrance" required maxlength="90">')}${field('Source type',`<select name="source"><option value="upload">Video file</option><option value="webcam">${UI.mode==='live'?'Processing-worker camera':'Browser webcam'}</option><option value="network">Network stream</option></select>`)}<div id="source-options"></div><div class="note">${UI.mode==='demo'?'Local sources support preview and zone setup. Connect the processing backend for person counting.':'The processing worker supplies count, density and inference measurements.'}</div>${footer('Add feed')}</form>`,stop);
 const form=$('#source-form'),opts=$('#source-options');
 function selection(){stop();opts.innerHTML=form.source.value==='upload'?field('Choose video','<input type="file" name="file" accept=".mp4,.mov,.avi,.mkv" required>'):form.source.value==='network'?field(UI.mode==='live'?'Stream address (HTTP, HTTPS or RTSP)':'Browser-playable HTTP or HTTPS video URL','<input type="url" name="url" placeholder="https://camera.example/stream.mp4" required>'):UI.mode==='live'?field('Worker camera index','<input type="number" name="device" min="0" step="1" value="0" required>'):`<div class="form"><button type="button" id="startcam">${icon('cam')} Enable camera preview</button><select aria-label="Camera device" id="devices" hidden></select><video id="cam-preview" style="max-height:160px;width:100%" muted autoplay playsinline hidden></video></div>`;if($('#startcam')){$('#startcam').onclick=()=>startCam();$('#devices').onchange=()=>startCam($('#devices').value);}}
 async function startCam(device){stop();const token=inFlight;try{if(!navigator.mediaDevices?.getUserMedia)throw Error('Camera access requires localhost or HTTPS and browser permission.');const next=await navigator.mediaDevices.getUserMedia({video:device?{deviceId:{exact:device}}:true,audio:false});if(token!==inFlight){next.getTracks().forEach(t=>t.stop());return;}stream=next;$('#cam-preview').srcObject=stream;$('#cam-preview').hidden=false;const list=(await navigator.mediaDevices.enumerateDevices()).filter(d=>d.kind==='videoinput');if(token!==inFlight)return;$('#devices').innerHTML=list.map(d=>`<option value="${esc(d.deviceId)}">${esc(d.label||'Camera')}</option>`).join('');$('#devices').value=stream.getVideoTracks()[0].getSettings().deviceId||'';$('#devices').hidden=list.length<2;$('#startcam').textContent='Refresh camera preview';form.querySelector('.form-error').textContent='';}catch(e){if(token===inFlight)form.querySelector('.form-error').textContent='Camera access failed. '+e.message;}}
 selection();form.source.onchange=selection;
 submitHandler(form,async()=>{
 const name=form.elements.name.value.trim(),locationName=form.elements.location.value.trim(),type=form.source.value;if(!name||!locationName)throw Error('Enter a feed name and a zone.');const file=form.file?.files[0];if(type==='upload'&&(!file||!file.size))throw Error('Choose a nonempty video file.');
 let url;if(type==='network'){url=new URL(form.url.value);if(!(UI.mode==='live'?['https:','http:','rtsp:']:['https:','http:']).includes(url.protocol))throw Error('Choose a supported stream protocol.');if(url.username||url.password)throw Error('Configure stream credentials on the worker, then use its stream address.');}
 let f;if(UI.mode==='live'){
   if(type==='upload'){const b=new FormData();b.append('file',file);b.append('name',name);b.append('location',locationName);f=await UI.adapter.call('/api/feeds/upload/','POST',b);}
   else f=await UI.adapter.call('/api/feeds/','POST',{source_type:type,name,location:locationName,source_url:url?.href,device_index:form.device?Number(form.device.value):undefined});
   f=f.feed||f;if(!f.feed_id)throw Error('The server did not return a feed ID.');
 }else{if(type==='webcam'&&!stream)throw Error('Enable the camera preview before adding this feed.');const id='camera-'+unique().slice(0,8);let media=url?.href;if(type==='upload'){media=URL.createObjectURL(file);UI.objectUrls.add(media);}
 f={feed_id:id,camera_label:'CAM '+String(UI.feeds.size+1).padStart(2,'0'),name,location:locationName,source_type:type,stream_state:type==='upload'?'replay':'connecting',analysis_state:'pending',severity:'unknown',calibrated:false,preview_transport:'video',preview_url:media,history:[]};
 if(stream){UI.streams.set(id,stream);stream=null;}}
 UI.feeds.set(f.feed_id,f);eventLog(f.feed_id,'info','Feed added',`${cap(type)} source registered.`);dialog.close();location.hash=href(f.feed_id);show();toast('Feed added. Open zone calibration to define its ground area.');
 });
}
function submitHandler(form,handler){form.onsubmit=async e=>{e.preventDefault();const btn=form.querySelector('[type=submit]'),original=btn.textContent;btn.disabled=true;btn.textContent='Saving…';form.querySelector('.form-error').textContent='';try{await handler();}catch(error){form.querySelector('.form-error').textContent=error.message;}finally{btn.disabled=false;btn.textContent=original;}};}
function calibration(f){
 if(!f)return;const media=document.querySelector('.detail-frame [data-media]');if(!media||f.preview_failed){toast('A camera frame is required for calibration.');return;}
 const w=media.videoWidth||media.naturalWidth,h=media.videoHeight||media.naturalHeight;if(!w||!h){toast('Wait for a camera frame before starting calibration.');return;}
 const canvas=document.createElement('canvas');canvas.width=w;canvas.height=h;canvas.getContext('2d').drawImage(media,0,0,w,h);
 calPoints=[];pendingCal=f.feed_id;
 open('Calibrate monitored zone',`<form id="cal-form" class="form"><p class="subtle">Select the four corners of a measured rectangle on the ground, in clockwise order. Enter its actual dimensions.</p><div id="cal-frame" class="cal-target" style="aspect-ratio:${w}/${h}" role="group" aria-label="Zone reference frame"><svg viewBox="0 0 100 100" preserveAspectRatio="none" id="cal-overlay"></svg></div><div class="split"><span id="point-count" class="subtle">0 of 4 corners selected</span><button type="button" data-action="reset-points">Reset points</button></div><details><summary>Enter normalized corner coordinates</summary><label class="field">Four x,y pairs, each from 0 to 1<input id="coordinates" placeholder="0.1,0.2 0.9,0.2 0.9,0.8 0.1,0.8"></label></details><div class="pair">${field('Ground width (m)','<input type="number" name="width" min=".01" max="10000" step="any" required>')}${field('Ground length (m)','<input type="number" name="lengthM" min=".01" max="10000" step="any" required>')}</div><span class="subtle" id="area-preview">Measured area — m²</span>${footer('Save calibration')}</form>`);
 canvas.style.cssText='position:absolute;inset:0;width:100%;height:100%';$('#cal-frame').prepend(canvas);
 $('#cal-frame').onclick=e=>{if(calPoints.length===4)return;const r=$('#cal-frame').getBoundingClientRect();calPoints.push([(e.clientX-r.left)/r.width,(e.clientY-r.top)/r.height]);paintPoints();};
 $('#coordinates').oninput=e=>{const raw=e.target.value;const pp=raw.trim().split(/\s+/).map(v=>v.split(',').map(n=>n.trim()===''?NaN:Number(n)));calPoints=pp.length===4&&pp.every(p=>p.length===2&&p.every(v=>Number.isFinite(v)&&v>=0&&v<=1))?pp:[];paintPoints(false);};
 const form=$('#cal-form');form.oninput=()=>{$('#area-preview').textContent='Measured area '+(form.width.value&&form.lengthM.value?fmt(Number(form.width.value)*Number(form.lengthM.value),2):'—')+' m²';};
 submitHandler(form,async()=>{if(pendingCal!==f.feed_id||calPoints.length!==4)throw Error('Select all four corners first.');const turns=calPoints.map(([ax,ay],i)=>{const [bx,by]=calPoints[(i+1)%4],[cx,cy]=calPoints[(i+2)%4];return (bx-ax)*(cy-by)-(by-ay)*(cx-bx);});if(!turns.every(x=>x>.00001)&&!turns.every(x=>x<-.00001))throw Error('Choose four distinct corners around the perimeter of a convex rectangle.');
 const width=Number(form.width.value),length=Number(form.lengthM.value),payload={reference_points:calPoints,coordinate_system:'normalized-top-left',width_m:width,length_m:length,zone_area_m2:width*length};
 if(UI.mode==='live'){const res=await UI.adapter.call(`/api/feeds/${freshId(f.feed_id)}/calibration/`,'PUT',payload);if(res.feed)Object.assign(f,res.feed);else if(res.calibrated===true)Object.assign(f,{calibrated:true,zone_area_m2:res.zone_area_m2??payload.zone_area_m2});}
 else Object.assign(f,{...payload,calibrated:true,people_count:null,density_people_per_m2:null,growth_rate:null,predicted_threshold_time:null,severity:'unknown',density_trend:'unknown',analysis_state:'pending',measured_fps:null,history:[]});
 eventLog(f.feed_id,'info','Zone geometry saved',`${fmt(payload.zone_area_m2,2)} m² measured ground area.`,'calibration');dialog.close();show();toast('Zone geometry saved. Awaiting measurements.');});
}
function paintPoints(syncInput=true){$('#cal-overlay').innerHTML=`<polygon points="${calPoints.map(p=>p.map(v=>v*100).join(',')).join(' ')}" fill="#abef8338" stroke="#b5f48a" stroke-width=".5"/>${calPoints.map(([x,y],i)=>`<circle cx="${x*100}" cy="${y*100}" r="1.5" fill="#bbf792"/><text x="${x*100+2}" y="${y*100}" fill="white" font-size="4">${i+1}</text>`).join('')}`;if(syncInput)$('#coordinates').value=calPoints.map(p=>p.map(v=>v.toFixed(3)).join(',')).join(' ');$('#point-count').textContent=calPoints.length+' of 4 corners selected';}
function settings(){open('Connection settings',`<form id="settings-form" class="form"><div class="form">${field('Backend origin',`<input type="url" name="origin" value="${esc(location.origin)}" required>`)}<p class="subtle">Live Django dashboard and Django Channels event stream.</p></div>${footer('Reconnect')}</form>`);
 const form=$('#settings-form');
 submitHandler(form,async()=>{
   const adapter=new EntropyData.Django(form.origin.value,receive,setLiveStatus);
   let snap=await adapter.call('/api/dashboard/');
   if(!Array.isArray(snap.feeds))throw Error('The server must return a dashboard snapshot with a feeds array.');
   if(!Array.isArray(snap.incidents)&&!Array.isArray(snap.active_incidents))snap.incidents=await adapter.call('/api/incidents/active/');
   switchData();UI.mode='live';UI.adapter=adapter;snapshot(snap);localStorage.setItem('antropy-backend',adapter.base);dialog.close();UI.route='overview';history.replaceState(null,'','#overview');adapter.start();show();
 });}
function setLiveStatus(s){setStatus(s);show();}
function updateMetrics(){metricTimer=null;if(UI.route.startsWith('feed/')){const f=UI.feeds.get(UI.route.slice(5));if(!f)return;const frame=$('.detail-frame');if(!frame)return;
 if(f.preview_transport==='image' && !f.fixture && f.preview_url){
   const media=frame.querySelector('[data-media],.fallback');
   if(media)media.outerHTML=markupMedia(f);
 }
 const metrics=frame.parentElement.querySelector('.details-grid');
 metrics.innerHTML=A.detailStats(f).map(pair=>A.metric(...pair)).join('');
 const badge=frame.parentElement.querySelector('.split .tag');if(badge)badge.outerHTML=A.tag(sev(f));
 frame.querySelector('.cam-labels').outerHTML=signal(f).split('<div class="frame-bottom">')[0];
 const stamp=frame.querySelector('.frame-bottom');stamp.innerHTML='<span class="stamp">'+esc(A.stream(f).toUpperCase())+'</span><span class="stamp">'+time(f.metric_timestamp)+'</span>';
 const chartPanel=frame.parentElement.nextElementSibling;if(chartPanel&&f.history?.length>1){chartPanel.innerHTML='<h2>Density history</h2>'+A.chart(f.history,'#b4e495','plot')+'<div class="graph-labels"><span>Earlier samples</span><span>'+fmt(f.density_people_per_m2,2)+' people/m² · Latest</span></div>';}
 return;}
 if(UI.route!=='overview'){if(UI.route==='diagnostics')show();return;}const strip=$('.kpis');if(strip)strip.innerHTML=kpis();const grid=$('.feed-grid');if(!grid)return;
 const byId=new Map([...grid.querySelectorAll('[data-card]')].map(el=>[el.dataset.card,el]));
 for(const f of UI.feeds.values()){const el=byId.get(f.feed_id);if(!el)continue;
 if(f.preview_transport==='image' && !f.fixture && f.preview_url){
   const media=el.querySelector('[data-media],.fallback');
   if(media)media.outerHTML=markupMedia(f);
 }
 el.className='card '+sev(f);el.querySelector('.stats-band').outerHTML=band(f);el.querySelector('.peek').innerHTML=peek(f);el.querySelector('.cam-labels').outerHTML=signal(f).split('<div class="frame-bottom">')[0];el.querySelector('.frame-bottom').innerHTML=`<span class="stamp"><i class="dot"></i>${esc(A.stream(f).toUpperCase())}</span><span class="stamp">${time(f.metric_timestamp)}</span>`;}
 if(Date.now()-UI.lastOrder>5000&&!grid.contains(document.activeElement)&&!grid.matches(':hover')){UI.lastOrder=Date.now();sortFeeds().forEach((f,i)=>{const el=byId.get(f.feed_id);if(el&&grid.children[i]!==el)grid.insertBefore(el,grid.children[i]||null);});}}
function receive(e){const kind=e.type,body=e.payload||e,inc=body.incident||body,fid=body.feed_id||body.feed?.feed_id||inc.feed_id;
 if(kind==='dashboard.snapshot')snapshot(body.snapshot||body);
 else if(kind.startsWith('incident.')){const id=inc.incident_id;if(!id)return;if(kind==='incident.resolved'||inc.state==='resolved')UI.incidents.delete(id);else UI.incidents.set(id,{...UI.incidents.get(id),...inc,incident_id:id,feed_id:fid||UI.incidents.get(id)?.feed_id,state:'active',acknowledged:kind==='incident.acknowledged'||(inc.acknowledged??UI.incidents.get(id)?.acknowledged??false)});
 const title=kind==='incident.resolved'?'Recovery confirmed':kind==='incident.acknowledged'?'Incident acknowledged':kind==='incident.created'?'Critical incident opened':'Incident updated';eventLog(fid,kind==='incident.resolved'?'normal':'critical',title,inc.reason||title,'crowd',e.event_id);if(kind==='incident.created'){$('#announcer').textContent=title+' at '+(UI.feeds.get(fid)?.name||fid);beep();toast(title);if(dialog.open)dialog.close();}}
 else if(kind==='feed.removed'){freeMedia(fid);UI.feeds.delete(fid);}
 else if(kind.startsWith('feed.')){if(!fid)return;const old=UI.feeds.get(fid)||{};const patch=body.metrics||body.feed||body.changes||body;const updated={...old,...patch,feed_id:fid};if(Number.isInteger(patch.version)&&patch.version<old.version)return;
 if(kind==='feed.metrics_updated'){updated.metric_timestamp=patch.metric_timestamp||e.timestamp;updated.history=Array.isArray(patch.history)?patch.history:(old.history||[]).concat(Number.isFinite(patch.density_people_per_m2)?[patch.density_people_per_m2]:[]).slice(-90);}
 UI.feeds.set(fid,updated);if(kind==='feed.metrics_updated'&&old.feed_id){if(!metricTimer)metricTimer=setTimeout(updateMetrics,650);return;}
 }else if(kind.startsWith('alert.')){const entry=body.alert||body.event||body;UI.events.set(entry.event_id||e.event_id,{...entry,event_id:entry.event_id||e.event_id});if(kind==='alert.created')toast(entry.message||'New crowd alert');}
 else return;
 show();}
function removeDialog(f){if(active().some(i=>i.feed_id===f.feed_id)){toast('This feed has an active critical incident.');return;}open('Remove camera feed',`<form class="form" id="remove-form"><p class="subtle">Remove ${esc(f.name)} from the control room and stop monitoring this source?</p>${footer('Remove feed')}</form>`);submitHandler($('#remove-form'),async()=>{if(UI.mode==='live')await UI.adapter.call(`/api/feeds/${freshId(f.feed_id)}/`,'DELETE');freeMedia(f.feed_id);UI.feeds.delete(f.feed_id);eventLog(f.feed_id,'info','Feed removed',f.name);dialog.close();location.hash='overview';});}
const actions={overlay:()=>{UI.hideOverlay=!UI.hideOverlay;show();},fullscreen:async()=>{const frame=$('.detail-frame');if(frame?.requestFullscreen)await frame.requestFullscreen();else toast('Fullscreen is unavailable in this browser.');},close:()=>dialog.close(),stats:b=>b.closest('.card').classList.toggle('show-stats'),add:()=>locks().length?guard():addDialog(),settings:()=>locks().length?guard():settings(),calibrate:()=>calibration(UI.feeds.get(UI.route.slice(5))),remove:()=>removeDialog(UI.feeds.get(UI.route.slice(5))),retry:()=>{UI.feeds.get(UI.route.slice(5)).preview_failed=false;show();},'reset-points':()=>{calPoints=[];paintPoints();},scenario:async()=>{const resolved=active().length>0;await saveDemoState({resolved,acknowledged:false});show();if(!resolved){beep();$('#announcer').textContent='New sample critical incident at Main Gate';}toast(resolved?'Sample recovery confirmed. Main Gate unpinned.':'New sample incident at Main Gate.');}};
document.addEventListener('click',async e=>{const b=e.target.closest('button');if(!b)return;try{if(b.id==='audio')await audioToggle();else if(b.dataset.ack){b.disabled=true;try{await ack(b.dataset.ack);}finally{b.disabled=false;}}else if(b.dataset.action)await actions[b.dataset.action]?.(b);else if(b.dataset.layout){UI.layout=b.dataset.layout;show();}else if(b.dataset.filter){UI.filter=b.dataset.filter;show();}}catch(err){toast(err.message);}});
document.addEventListener('change',e=>{if(e.target.id==='sort'){UI.sort=e.target.value;show();}});
document.addEventListener('error',e=>{const id=e.target.dataset?.media,f=UI.feeds.get(id);if(f&&!f.preview_failed){f.preview_failed=true;e.target.replaceWith(Object.assign(document.createElement('div'),{className:'fallback',textContent:'Preview unavailable'}));if(!f.fixture&&UI.mode==='demo')f.stream_state='error';}},true);
document.addEventListener('loadeddata',e=>{const f=UI.feeds.get(e.target.dataset?.media);if(f&&UI.mode==='demo'&&f.stream_state==='connecting'){f.stream_state='live';if(!metricTimer)metricTimer=setTimeout(updateMetrics,100);}},true);
window.addEventListener('hashchange',navigate);
document.addEventListener('click',e=>{const a=e.target.closest('a[href^="#"]');if(!a)return;const dest=decodeURIComponent(a.hash.slice(1));if(dest!==UI.route&&guarded(dest)){e.preventDefault();guard();}else if(dialog.open)dialog.close();});
async function init(){document.querySelectorAll('[data-i]').forEach(el=>el.outerHTML=icon(el.dataset.i));UI.mode='live';
 try{
   UI.adapter=new EntropyData.Django(location.origin,receive,setLiveStatus);
   const snap=await UI.adapter.call('/api/dashboard/');
   snapshot(snap);localStorage.setItem('antropy-backend',location.origin);UI.adapter.start();
 }catch(error){
   setStatus('Disconnected');
   snapshot({feeds:[],active_incidents:[],events:[]});
   toast(error.message);
 }
 const route=readRoute();if(route==='overview'||!guarded(route))UI.route=route;else{history.replaceState(null,'','#overview');guard();}show();
 let refreshing=false;
 setInterval(async()=>{
   const adapter=UI.adapter;
   if(UI.mode!=='live'||!adapter||refreshing)return;
   refreshing=true;
   try {
     const {results}=await adapter.call('/api/feeds/');
     if(adapter!==UI.adapter)return;
     for(const feed of results){
       const current=UI.feeds.get(feed.feed_id);
       if(current)Object.assign(current,feed);
     }
     updateMetrics();
   } catch { /* Keep the latest sample while reconnecting. */ }
   finally {refreshing=false;}
 },5000);
}
init();
})();
