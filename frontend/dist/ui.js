(function(){
'use strict';
const paths={
grid:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z', log:'M5 3h14v18H5z M8 7h8 M8 11h8 M8 15h5',
pulse:'M2 12h5l3-8 4 16 3-8h5',muted:'M3 9h4l5-4v14l-5-4H3z M16 9l6 6 M22 9l-6 6',sound:'M3 9h4l5-4v14l-5-4H3z M16 8q4 4 0 8 M19 5q7 7 0 14',pin:'M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0z M14 10a2 2 0 1 1-4 0 2 2 0 1 1 4 0z',plus:'M12 5v14 M5 12h14',
cam:'M3 6h12v12H3z M15 10l6-3v10l-6-3',people:'M15 20v-2a5 5 0 0 0-10 0v2 M13 7a3 3 0 1 1-6 0 3 3 0 1 1 6 0z M16 4q5 3 0 6 M18 13q4 1 4 6',density:'M3 9V3h6 M15 3h6v6 M21 15v6h-6 M9 21H3v-6 M9 9h6v6H9z',bell:'M4 17h16l-2-3V9a6 6 0 0 0-12 0v5z M10 20q2 2 4 0',
sort:'M3 5h17 M3 11h12 M3 17h7',down:'m6 9 6 6 6-6',list:'M4 5h16 M4 12h16 M4 19h16',expand:'M14 4h6v6 M20 4l-7 7 M10 20H4v-6 M4 20l7-7',rising:'m3 16 6-6 4 4 8-9 M15 5h6v6',falling:'m3 6 6 6 4-4 8 9 M15 17h6v-6',stable:'M3 12h17 M15 7l5 5-5 5',
warn:'m12 3 10 17H2z M12 9v4 M12 16h.01',check:'m4 12 5 5L20 6',clock:'M21 12a9 9 0 1 1-18 0 9 9 0 1 1 18 0z M12 7v5l3 2',cross:'m5 5 14 14 M19 5 5 19',back:'m14 5-7 7 7 7',focus:'M4 9V4h5 M15 4h5v5 M20 15v5h-5 M9 20H4v-5 M9 12h6 M12 9v6',bookmark:'M6 3h12v18l-6-4-6 4z',activity:'M4 20V10 M10 20V4 M16 20V9 M22 20V6',file:'M5 2h9l5 5v15H5z M14 2v6h5',network:'M4 5q8-6 16 0 M6 9q6-5 12 0 M9 13q3-3 6 0 M12 17h.01',tune:'M3 6h6 M13 6h8 M3 17h11 M18 17h3 M9 3v6 M15 14v6',info:'M21 12a9 9 0 1 1-18 0 9 9 0 1 1 18 0z M12 11v6 M12 7h.01',target:'M3 8V3h5 M16 3h5v5 M21 16v5h-5 M8 21H3v-5 M9 9h6v6H9z'
};
const icon=k=>`<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[k]||paths.info}"/></svg>`;
const esc=x=>String(x??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const $=s=>document.querySelector(s);
const UI={feeds:new Map(), incidents:new Map(), events:new Map(),mode:'demo',status:"",sort:'risk',layout:'grid',filter:'All',route:'overview',adapter:null,audio:null,streams:new Map(),objectUrls:new Set(),lastOrder:0,staleAfter:15};
const active=()=>[...UI.incidents.values()].filter(i=>i.state==='active');
const locks=()=>active().filter(i=>!i.acknowledged);
const stale=f=>!f.fixture&&(f.stream_state==='stale'||(UI.mode==='live'&&(UI.status!=='Connected'||(!f.metric_timestamp||Date.now()-Date.parse(f.metric_timestamp)>UI.staleAfter*1000))));
const sev=f=>active().some(i=>i.feed_id===f.feed_id)?'critical':(!f.calibrated||stale(f)||['offline','error'].includes(f.stream_state)?'unknown':(['critical','high','elevated','normal'].includes(f.severity)?f.severity:'unknown'));
const ranks={critical:5,high:4,elevated:3,normal:2,unknown:0};
const cap=x=>String(x||'unknown').replace(/_/g,' ').replace(/^./,c=>c.toUpperCase());
const fmt=(x,n=0)=>typeof x==='number'&&Number.isFinite(x)?x.toLocaleString('en-GB',{minimumFractionDigits:n,maximumFractionDigits:n}):'—';
const density=f=>f.calibrated?fmt(f.density_people_per_m2,2):'—';
const time=t=>!t||!Number.isFinite(Date.parse(t))?'—':new Date(t).toLocaleTimeString('en-GB',{hour12:false});
const stream=f=>stale(f)?'Stale':f.fixture?'Sample frame':cap(f.stream_state);
const validMetric=f=>f.fixture || (
  !stale(f)
  && f.calibrated
  && (
    f.is_valid===true
    || f.latest_metric?.is_valid===true
    || f.latest_metrics?.is_valid===true
  )
);
const unvalidatedPeople=f=>(
  !stale(f)
  && f.latest_metric
  && f.latest_metric.is_valid===false
  && Number.isFinite(f.latest_metric.people_count)
)
  ? f.latest_metric.people_count
  : (
    !stale(f)
    && f.latest_metrics
    && f.latest_metrics.is_valid===false
    && Number.isFinite(f.latest_metrics.people_count)
  )
    ? f.latest_metrics.people_count
    : (
      !stale(f)
      && f.is_valid===false
      && Number.isFinite(f.people_count)
    )
      ? f.people_count
      : null;
const latestMetric=f=>(
  f.latest_metric && typeof f.latest_metric==='object'
    ? f.latest_metric
    : f.latest_metrics && typeof f.latest_metrics==='object'
      ? f.latest_metrics
      : null
);
const metricValue=(f,key)=>{
  const metric=latestMetric(f);
  if(metric&&Number.isFinite(metric[key]))return metric[key];
  if(Number.isFinite(f[key]))return f[key];
  return null;
};
const metricTimestamp=f=>{
  const metric=latestMetric(f);
  if(metric?.metric_timestamp)return metric.metric_timestamp;
  if(metric?.captured_at)return metric.captured_at;
  return f.metric_timestamp||null;
};
const href=id=>'#feed/'+encodeURIComponent(id);
const safeUrl=u=>{try{const x=new URL(u,UI.adapter?.base||location.href);return ['https:','http:'].includes(x.protocol)||UI.objectUrls.has(x.href)||(location.protocol==='file:'&&String(u).startsWith('assets/'))?esc(x.href):'';}catch{return '';}};
const tag=s=>`<span class="tag ${esc(s)}"><i class="dot"></i>${esc(s==='unknown'?'Unassessed':s)}</span>`;
function markupMedia(f,thumb=false){
  const url=f.preview_url?safeUrl(f.preview_url):'';
  if(f.preview_failed||['error','offline'].includes(f.stream_state)||(!url&&!UI.streams.has(f.feed_id)))return `<div class="fallback">${icon('cam')}<span>${esc(f.preview_failed?'Preview unavailable':f.stream_state==='offline'?'Camera offline':'Waiting for video')}</span></div>`;
  if(['image','mjpeg'].includes(f.preview_transport))return `<img class="${thumb?'thumb':f.fixture?'sample':''}" src="${url}" alt="${esc(f.name)} camera view" data-media="${esc(f.feed_id)}">`;
  return `<video ${thumb?'class="thumb"':''} data-media="${esc(f.feed_id)}" ${url?`src="${url}"`:''} muted autoplay playsinline ${f.source_type==='upload'?'loop':''}></video>`;
}
// Reference-frame annotations are authored against the four 836 × 470 stills.
// Live feeds use the worker's annotated frames and never inherit these boxes.
const referenceBoxes={
 gate:[[216,234,37,84],[290,294,36,87],[324,292,26,89],[682,177,26,69],[568,274,29,95],[99,187,27,81],[374,155,26,73],[462,233,26,72]],
 food:[[380,234,54,161],[352,163,39,98],[503,176,36,110],[537,183,34,111],[577,255,41,146],[309,122,32,94],[239,133,37,80]],
 lawn:[[466,296,24,53],[495,295,18,54],[483,235,16,51],[523,212,18,46],[363,204,17,44],[594,200,17,44]],
 walk:[[332,254,34,92],[369,256,35,95],[408,160,23,59],[251,223,29,79],[395,111,18,51]]
};
function overlay(f){if(!f.fixture||!referenceBoxes[f.feed_id]||UI.hideOverlay)return '';return `<svg class="sample-overlay" viewBox="0 0 836 470" preserveAspectRatio="xMidYMid slice" aria-hidden="true">${referenceBoxes[f.feed_id].map(([x,y,w,h])=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="#b6ef8109" stroke="#c5fa9a" stroke-width="1.5"/><path d="M${x} ${y+6}v-6h8" fill="none" stroke="#c5fa9a" stroke-width="3"/>`).join('')}</svg>`;}
function signal(f){const s=sev(f);return `<div class="cam-labels"><span class="camera-id">${icon('cam')}${esc(f.camera_label||f.feed_id)}</span>${tag(s)}</div><div class="frame-bottom"><span class="stamp"><i class="dot"></i>${esc(stream(f).toUpperCase())}</span><span class="stamp">${time(f.metric_timestamp)}</span></div>${overlay(f)}`;}
function metric(label,value){return `<div class="metric"><small>${label}</small><strong>${value}</strong></div>`;}
function band(f){const valid=validMetric(f);const unvalidated=unvalidatedPeople(f);const people=valid&&Number.isFinite(f.people_count)?f.people_count:unvalidated;const densityValue=metricValue(f,'density_people_per_m2');const tr=valid&&['rising','stable','falling'].includes(f.density_trend)?f.density_trend:'unknown';return `<div class="stats-band">${metric('People',people!==null?`${fmt(people)}${valid?'':' <em>unvalidated</em>'}`:'—')}${metric('Density',densityValue!==null?`${fmt(densityValue,2)} <em>p/m²</em>`:'Unvalidated')}<div class="metric"><small>Trend</small><strong class="trend">${valid?icon(tr):icon('stable')}${valid?esc(cap(tr)):'Unknown'}</strong></div></div>`;}
const predicted=f=>!stale(f)&&f.predicted_threshold_time&&Date.parse(f.predicted_threshold_time)>Date.parse(f.metric_timestamp)?`~${Math.ceil((Date.parse(f.predicted_threshold_time)-Date.parse(f.metric_timestamp))/60000)} min from sample`:'No estimate';
function peek(f){const valid=validMetric(f);const people=valid&&Number.isFinite(f.people_count)?f.people_count:unvalidatedPeople(f);const fps=metricValue(f,'measured_fps');const timestamp=metricTimestamp(f);const densityValue=metricValue(f,'density_people_per_m2');return `Area ${fmt(f.zone_area_m2,1)} m² · ${f.calibrated?'Calibrated':'Calibration needed'}<br>People ${people!==null?fmt(people)+(valid?'':' unvalidated'):'—'} · Density ${densityValue!==null?fmt(densityValue,2)+' p/m²':'Unvalidated'}<br>Rate ${valid&&Number.isFinite(f.growth_rate)?fmt(f.growth_rate,2):'Unvalidated'} p/m²/min · ${fps!==null?fmt(fps,1):'—'} FPS<br>Sample ${timestamp?time(timestamp):'—'} · ${esc(stream(f))}`;}
function feedCard(f){return `<article class="card ${sev(f)}" data-card="${esc(f.feed_id)}"><a class="card-link" href="${href(f.feed_id)}" aria-label="Monitor ${esc(f.name)}"><div class="frame">${markupMedia(f)}${signal(f)}<div class="peek">${peek(f)}</div></div><div class="card-info"><div class="card-title"><h3>${esc(f.name)}</h3>${icon('expand')}</div><div class="card-location">${esc(f.location||'Unassigned location')}</div>${band(f)}</div></a><button class="peek-toggle" data-action="stats" title="Show camera statistics" aria-label="Show camera statistics">${icon('activity')}</button></article>`;}
function sortFeeds(){const items=[...UI.feeds.values()];return items.sort((a,b)=>{if(UI.sort==='name')return String(a.name).localeCompare(b.name);if(UI.sort==='density')return (b.calibrated?b.density_people_per_m2:-1)-(a.calibrated?a.density_people_per_m2:-1);if(UI.sort==='growth')return (b.growth_rate??-Infinity)-(a.growth_rate??-Infinity);return ranks[sev(b)]-ranks[sev(a)]||(b.risk_score??-1)-(a.risk_score??-1)||(Date.parse(a.predicted_threshold_time)||Infinity)-(Date.parse(b.predicted_threshold_time)||Infinity)||(b.density_people_per_m2??-1)-(a.density_people_per_m2??-1)||(b.people_count??-1)-(a.people_count??-1);});}
function chart(values,color,cls='mini-plot',bars=false,baseline=null){const arr=(values||[]).filter(Number.isFinite);if(arr.length<2)return '';const w=160,h=50,lo=baseline??Math.min(...arr)-.03,hi=Math.max(...arr,lo+.02)+.03;const pts=arr.map((v,i)=>[i*w/(arr.length-1),h-4-(v-lo)/(hi-lo)*(h-8)]);return `<svg class="${cls}" viewBox="0 0 160 50" preserveAspectRatio="none" aria-hidden="true">${[12,28,44].map(y=>`<path d="M0 ${y}h160" stroke="#354038" stroke-width=".6" stroke-dasharray="3 5"/>`).join('')}${bars?pts.map(([x,y])=>`<rect x="${x*.94}" y="${y}" width="7" height="${50-y}" rx="1.3" fill="${color}" opacity=".8"/>`).join(''):`<polygon points="0,50 ${pts.map(p=>p.join(',')).join(' ')} 160,50" fill="${color}" opacity=".07"/><polyline points="${pts.map(p=>p.join(',')).join(' ')}" fill="none" stroke="${color}" stroke-width="1.7" vector-effect="non-scaling-stroke"/>`}</svg>`;}
function kpis(){
 const all=[...UI.feeds.values()],measured=all.filter(f=>!stale(f)&&!['offline','error'].includes(f.stream_state)&&(validMetric(f)&&Number.isFinite(f.people_count)||unvalidatedPeople(f)!==null)),peak=all.filter(f=>validMetric(f)&&f.calibrated&&Number.isFinite(f.density_people_per_m2)).sort((a,b)=>b.density_people_per_m2-a.density_people_per_m2)[0];
 const count=measured.reduce((acc,f)=>acc+(validMetric(f)&&Number.isFinite(f.people_count)?f.people_count:unvalidatedPeople(f)||0),0),crit=active().length,warn=all.filter(f=>sev(f)==='high').length, online=all.filter(f=>!stale(f)&&['live','replay'].includes(f.stream_state)).length;
 const sample=all.filter(f=>f.fixture&&Array.isArray(f.history)),history=sample.length?sample[0].history.map((_,i)=>sample.reduce((a,f)=>a+Math.round(f.history[i]*f.zone_area_m2),0)):[];
 const cards=[['cam','Active feeds',fmt(online),`of ${all.length} configured`,barsForFeeds(all)],['people','People detected',measured.length?fmt(count):'—','Across monitored feeds',chart(history,'#b1dd96')],['density','Peak density',`${peak?density(peak):'—'}<small>p/m²</small>`,peak?esc(peak.name):'Awaiting calibration',chart(peak?.history,'#e0c48b')],['bell','Active alerts',fmt(crit+warn),`${crit} critical · ${warn} high`,alertBars(all)]];
 return cards.map(([i,l,v,n,c])=>`<div class="kpi"><div class="kpi-label">${icon(i)}${l}</div><div class="kpi-value">${v}</div><div class="kpi-note">${n}</div>${c}</div>`).join('');
}
function barsForFeeds(all){return `<svg class="mini-plot" viewBox="0 0 84 28" aria-hidden="true">${all.slice(0,8).map((f,i)=>`<g fill="${stale(f)?'#718077':'#a9d398'}"><rect x="${i*10+2}" y="7" width="6" height="16" rx="1.4"/><rect x="${i*10+2}" y="3" width="6" height="2" rx="1"/></g>`).join('')}</svg>`;}
function alertBars(all){const colors={critical:'#ef8d80',high:'#d9a177',normal:'#526956',elevated:'#988d60',unknown:'#646d66'};return `<svg class="mini-plot" viewBox="0 0 84 28" aria-hidden="true">${all.slice(0,8).map((f,i)=>`<rect x="${i*10+3}" y="${24-Math.max(1,ranks[sev(f)])*4}" width="6" height="${Math.max(1,ranks[sev(f)])*4}" fill="${colors[sev(f)]}" rx="1"/>`).join('')}</svg>`;}
const select=(id,options,value,i='sort')=>`<label class="selectbox">${icon(i)}<select id="${id}" aria-label="${esc(id)}">${options.map(([v,l])=>`<option value="${esc(v)}" ${v===value?'selected':''}>${esc(l)}</option>`).join('')}</select>${icon('down')}</label>`;
function heading(kicker,title,sub,buttons=''){return `<div class="heading"><div><div class="eyebrow">${kicker}</div><h1>${esc(title)}</h1><div class="venue">${sub}</div></div><div class="actions">${buttons}</div></div>`;}
const addBtn=`<button class="primary" data-action="add">${icon('plus')} Add feed</button>`;
const venue=`${icon('pin')}Campus Fest 2026 <span class="sep">/</span><span class="venue-location">Lovely Professional University</span>`;
const tabs=()=>`<div class="tabs" aria-label="Event filters">${['All','Alerts','System'].map(x=>`<button data-filter="${x}" class="${UI.filter===x?'active':''}" aria-pressed="${UI.filter===x}">${x}</button>`).join('')}</div>`;
function events(feedId,compact=false){const rows=[...UI.events.values()].filter(e=>(!feedId||e.feed_id===feedId)&&(UI.filter==='All'||(UI.filter==='System'?['system','calibration'].includes(e.category):['high','critical','elevated'].includes(e.severity)))).sort((a,b)=>Date.parse(b.timestamp)-Date.parse(a.timestamp));
 return rows.slice(0,compact?24:250).map(e=>{const f=UI.feeds.get(e.feed_id),s=Object.hasOwn(ranks,e.severity)?e.severity:'info',symbol=e.category==='calibration'?'focus':e.category==='system'?'cam':e.category==='prediction'?'rising':s==='critical'?'warn':s==='normal'?'check':'pulse';return `<${f?'a':'div'} ${f?`href="${href(f.feed_id)}"`:''} class="event ${s}"><span class="event-icon">${icon(symbol)}</span><div class="event-copy"><div class="event-meta"><span>${esc(f?.name||e.feed_name||'System')}</span><time datetime="${esc(e.timestamp)}">${time(e.timestamp)}</time></div><strong>${esc(e.title||cap(e.event_type||e.category))}</strong><p>${esc(e.message)}</p></div></${f?'a':'div'}>`;}).join('')||'<p class="empty">No events match this view.</p>';}
function activity(feedId='',compact=true){return `<section class="panel ${compact?'':'wide-event'}"><div class="rail-head"><h2>${icon('pulse')}${feedId?'Zone activity':compact?'Activity log':'Event history'}</h2><span class="rail-stamp">NEWEST FIRST</span></div>${tabs()}<div class="timeline" data-history="${esc(feedId)}">${events(feedId,compact)}</div>${compact?`<a class="rail-foot" href="#events">${icon('log')} View event log</a>`:''}</section>`;}
function dock(){const incidents=active();if(!incidents.length)return '';return `<section class="panel dock"><div class="rail-head"><h2>${icon('bookmark')} Pinned critical ${incidents.length>1?'zones':'zone'}</h2><span class="rail-stamp">${incidents.length} ACTIVE</span></div>${incidents.map(i=>{const f=UI.feeds.get(i.feed_id);return `<div class="pin-item"><div class="pin-main">${f?`<a href="${href(i.feed_id)}" aria-label="Inspect ${esc(f.name)}">${markupMedia(f,true)}</a>`:''}<a href="${href(i.feed_id)}"><strong>${esc(f?.name||i.feed_id)}</strong><small>${i.acknowledged?'Acknowledged':'Needs acknowledgement'}</small></a>${i.acknowledged?'':`<button class="ack" data-ack="${esc(i.incident_id)}">Acknowledge</button>`}</div></div>`;}).join('')}</section>`;}
function rail(){return `<aside class="rail">${activity()}${dock()}</aside>`;}
function overview(){return `${heading('Control room','Monitoring overview',venue,addBtn)}<section class="kpis" aria-label="Monitoring summary">${kpis()}</section><div class="work"><section><div class="section-head"><div class="title-group"><h2>Camera feeds</h2><span class="count-tag">${String(UI.feeds.size).padStart(2,'0')}</span></div><div class="controls">${select('sort',[['risk','Highest risk first'],['density','Highest density'],['growth','Fastest rising'],['name','Camera name']],UI.sort)}<div class="view-switch">${['grid','list'].map(v=>`<button title="${v} view" aria-label="${v} view" aria-pressed="${UI.layout===v}" data-layout="${v}" class="${UI.layout===v?'selected':''}">${icon(v)}</button>`).join('')}</div></div></div><div class="feed-grid ${UI.layout==='list'?'list-mode':''}">${sortFeeds().map(feedCard).join('')||'<div class="empty">No camera feeds yet. Add a feed to start monitoring.</div>'}</div></section>${rail()}</div>`;}
function detailStats(f){const valid=validMetric(f);const people=valid&&Number.isFinite(f.people_count)?f.people_count:unvalidatedPeople(f);const densityValue=metricValue(f,'density_people_per_m2');const growth=metricValue(f,'growth_rate');const fps=metricValue(f,'measured_fps');const timestamp=metricTimestamp(f);return [['People detected',people!==null?`${fmt(people)}${valid?'':' (unvalidated)'}`:'—'],['Density (people/m²)',densityValue!==null?fmt(densityValue,2):valid?'—':'Unvalidated'],['Trend',valid&&f.density_trend?esc(cap(f.density_trend)):'Unvalidated'],['Growth (p/m²/min)',growth!==null?valid?fmt(growth,2):`${fmt(growth,2)} (unvalidated)`:'Unvalidated'],['Estimated limit crossing',valid?esc(predicted(f)):'No estimate'],['Inference FPS',fps!==null?`${fmt(fps,1)}${valid?'':' (unvalidated)'}`:'—'],['Latest sample',timestamp?time(timestamp):'—'],['Calibration',f.calibrated?fmt(f.zone_area_m2,1)+' m²':'Required']]}
function feedDetail(id){const f=UI.feeds.get(id);if(!f)return `${heading('Camera feeds','Feed unavailable','This feed is no longer configured.')}<a class="btn" href="#overview">Return to overview</a>${dock()}`;
 const history=f.history?.filter(Number.isFinite)||[],stats=detailStats(f);
 return `<a class="back" href="#overview">${icon('back')} Monitoring overview</a>${heading('Feed monitor',f.name,`${icon('pin')}${esc(f.location||'Unassigned')} · ${esc(f.camera_label||id)}`,`<button data-action="calibrate">${icon('focus')} Calibrate zone</button>`)}<div class="work"><div class="page-body"><section class="panel"><div class="frame detail-frame">${markupMedia(f)}${signal(f)}</div><div class="viewer-tools"><span>${icon(f.fixture?'file':'cam')} ${esc(f.fixture?'Sample reference frame':stream(f))}</span>${f.fixture?`<button data-action="overlay" aria-pressed="${!UI.hideOverlay}">${icon('focus')} Sample boxes ${UI.hideOverlay?'off':'on'}</button>`:''}<button data-action="fullscreen">${icon('expand')} Fullscreen</button></div><div class="panel-pad"><div class="split"><h2>Zone measurements</h2>${tag(sev(f))}</div><div class="details-grid">${stats.map(x=>metric(...x)).join('')}</div></div></section><section class="panel panel-pad"><h2>Density history</h2>${history.length>1?`${chart(history,'#b4e495','plot')}<div class="graph-labels"><span>Earlier samples</span><span>${density(f)} people/m² · Latest</span></div>`:'<p class="subtle">Waiting for calibrated density samples.</p>'}</section><section class="panel panel-pad"><div class="split"><h2>Camera diagnostics</h2><button data-action="remove">${icon('cam')} Remove feed</button></div><div class="details-grid">${metric('Source',esc(cap(f.source_type)))}${metric('Preview',esc(stream(f)))}${metric('Analysis',esc(cap(f.analysis_state)))}${metric('Count error',Number.isFinite(f.count_error_percent)?fmt(f.count_error_percent,1)+'%':'Unevaluated')}</div>${f.preview_failed?'<button data-action="retry">Retry preview</button>':''}</section></div><aside class="rail">${dock()}${activity(id,false)}</aside></div>`;}
function diagnostics(){return `${heading('Control room','Diagnostics','Processing measurements and camera health.',`<button data-action="settings">${icon('tune')} Connection settings</button>`)}<div class="work"><div class="page-body"><section class="panel"><div class="rail-head"><h2>Feed health</h2></div><div class="table-wrap"><table><thead><tr>${['Camera','Preview','Analysis','Inference FPS','Count error','Latest sample'].map(s=>`<th>${s}</th>`).join('')}</tr></thead><tbody>${sortFeeds().map(f=>{const valid=validMetric(f);const fps=metricValue(f,'measured_fps');const timestamp=metricTimestamp(f);return `<tr><td><a href="${href(f.feed_id)}">${esc(f.name)}</a></td><td>${esc(stream(f))}</td><td>${esc(cap(f.analysis_state))}</td><td>${fps!==null?`${fmt(fps,1)}${valid?'':' (unvalidated)'}`:'—'}</td><td>${valid&&Number.isFinite(f.count_error_percent)?fmt(f.count_error_percent,1)+'%':'Unevaluated'}</td><td>${timestamp?time(timestamp):'—'}</td></tr>`}).join('')}</tbody></table></div></section><section class="panel panel-pad"><h2>Performance targets</h2><div class="details-grid">${metric('Concurrent feeds','2 or more')}${metric('Inference rate','5+ FPS')}${metric('Count error','Under 20%')}</div><p class="subtle" style="margin-top:16px">Validation requires labeled footage and measured inference results from the processing worker.</p></section>${UI.mode==='demo'?`<section class="panel panel-pad"><div class="split"><div><h2>Incident simulation</h2><p class="subtle">Step through a sample backend incident and its confirmed recovery.</p></div><button data-action="scenario">${active().length?'Simulate recovery':'Simulate incident'}</button></div></section>`:''}</div>${rail()}</div>`;}
function show(){
 const r=UI.route;document.title=(r.startsWith('feed/')?(UI.feeds.get(r.slice(5))?.name||'Feed monitor'):r==='overview'?'Monitoring overview':cap(r))+' · Entropy';
 $('#app').innerHTML=(r==='overview'?overview():r==='diagnostics'?diagnostics():r==='events'?`${heading('Control room','Event log','Chronological activity across monitored zones.')}<div class="work"><section>${activity('',false)}</section><aside class="rail">${dock()}</aside></div>`:feedDetail(r.slice(5)))+`<footer class="bottom-bar"><span>${icon('density')}${UI.mode==='demo'?'Sample camera imagery and telemetry':esc(UI.status)+' · Django dashboard'}</span><span>${icon('clock')}Local time · ${esc(Intl.DateTimeFormat().resolvedOptions().timeZone)}</span></footer>`;
 document.querySelectorAll('[data-nav]').forEach(n=>{const yes=n.dataset.nav===(r.startsWith('feed/')?'overview':r);n.classList.toggle('active',yes);if(yes)n.setAttribute('aria-current','page');else n.removeAttribute('aria-current');});bindMedia();
}
function bindMedia(){document.querySelectorAll('video[data-media]').forEach(v=>{const stream=UI.streams.get(v.dataset.media);if(stream&&v.srcObject!==stream)v.srcObject=stream;});}
Object.assign(window,{A:{detailStats,chart,UI,esc,icon,$,cap,time,fmt,active,locks,stale,sev,href,tag,metric,markupMedia,signal,band,peek,sortFeeds,kpis,events,show,bindMedia,feedCard,stream}});
})();
