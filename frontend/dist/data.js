/* The demo adapter is a local fixture service. The live adapter consumes the
   Django contract in the brief. Only incident messages/snapshots clear a pin. */
window.AntropyData = (() => {
  const ago = seconds => new Date(Date.now() - seconds * 1000).toISOString();
  const definitions = [
    ['gate','Main Gate','North entrance', 'critical',186,48.5,0.14,'gate', [2.2,2.26,2.19,2.51,2.46,2.66,2.61,2.93,2.84,3.15,3.1,3.42,3.38,3.67,3.84]],
    ['food','Food Court','East courtyard','high',142,52,0.11,'food',[1.1,1.25,1.22,1.46,1.39,1.64,1.58,1.68,1.92,1.88,2.17,2.24,2.18,2.49,2.73]],
    ['lawn','Stage Lawn','Central grounds','elevated',104,65,0.03,'lawn',[1.04,1.13,1.1,1.23,1.18,1.28,1.23,1.31,1.25,1.38,1.32,1.43,1.37,1.56,1.6]],
    ['walk','Library Walk','West pedestrian path','normal',54,75,0,'walk',[.69,.7,.71,.67,.69,.7,.69,.73,.72,.69,.71,.7,.73,.71,.72]]
  ];
  const seedEvents = [
    ['gate','critical','Density threshold crossed','The monitored zone crossed its configured limit.','crowd',8],
    ['food','high','Threshold approaching','Estimated crossing in 2 min at the current rate.','prediction',42],
    ['lawn','elevated','Density rising','A sustained increase was detected in this zone.','crowd',96],
    ['walk','normal','Zone returned to normal','Density settled below the recovery threshold.','crowd',172],
    ['food','info','Calibration complete','Ground area confirmed at 52 m².','calibration',237],
    ['gate','info','Feed connected','Camera preview and analysis are available.','system',352]
  ];
  function demoSnapshot() {
    const feeds=definitions.map(([id,name,location,severity,count,area,rate,img,history],i)=>({
      feed_id:id,camera_label:'CAM '+String(i+1).padStart(2,'0'),name,location,severity,people_count:count,zone_area_m2:area,
      calibrated:true,density_people_per_m2:count/area,density_trend:rate?'rising':'stable',growth_rate:rate,
      predicted_threshold_time:id==='food'?new Date(Date.now()+120000).toISOString():null,
      risk_score:98-i*24,stream_state:'replay',source_type:'fixture',preview_transport:'image',preview_url:'assets/'+img+'.jpg',
      analysis_state:'sample',metric_timestamp:ago(0),measured_fps:null,history, fixture:true
    }));
    return {feeds,incidents:[{incident_id:'sample-gate',feed_id:'gate',state:'active',acknowledged:false,reason:'Configured density limit crossed.'}],
      events:seedEvents.map(([feed_id,severity,title,message,category,s],i)=>({event_id:'fixture-'+i,feed_id,severity,title,message,category,timestamp:ago(s)}))};
  }
  const request = async (base,path,method='GET',body) => {
    const headers={Accept:'application/json'};
    const csrf=document.cookie.split('; ').find(x=>x.startsWith('csrftoken='))?.slice(10);
    if(csrf && new URL(base).origin===location.origin) headers['X-CSRFToken']=decodeURIComponent(csrf);
    if(body && !(body instanceof FormData)) headers['Content-Type']='application/json';
    const res=await fetch(base+path,{method,credentials:'include',headers,body:body instanceof FormData?body:JSON.stringify(body),signal:AbortSignal.timeout(20000)});
    if(!res.ok) throw new Error('The server returned '+res.status+'. Check the connection and account permissions.');
    return res.status===204?{}:res.json();
  };
  class Django {
    constructor(url,notify,status){const u=new URL(url);if(!['https:','http:'].includes(u.protocol)||u.username||u.password)throw Error('Enter an HTTP or HTTPS backend origin.');this.base=u.origin;this.notify=notify;this.status=status;this.seen=new Set();this.delay=1000;}
    call(path,method,body){return request(this.base,path,method,body);}
    start(){this.closed=false;this.connect();}
    async connect(){
      if(this.closed)return;
      this.status('Connecting');
      const ws=new WebSocket(this.base.replace(/^http/,'ws')+'/ws/dashboard/');this.ws=ws;
      let ready=false;const queue=[];
      ws.onopen=async()=>{
        try{
          const snap=await this.call('/api/dashboard/');
          if(!Array.isArray(snap.feeds))throw Error('Dashboard snapshot must include feeds.');
          if(!Array.isArray(snap.incidents)&&!Array.isArray(snap.active_incidents))snap.incidents=await this.call('/api/incidents/active/');
          if(ws!==this.ws||ws.readyState!==1)return;
          this.notify({type:'dashboard.snapshot',...{snapshot:snap}});this.seq=snap.sequence;
          ready=true;this.delay=1000;this.status('Connected');queue.forEach(receive);
        }catch{ws.close();}
      };
      const receive=e=>{
        if(ws!==this.ws||ws.readyState!==1)return;
        if(!e?.type||this.seen.has(e.event_id))return;
        if(Number.isInteger(e.sequence)&&Number.isInteger(this.seq)){
          if(e.sequence<=this.seq)return;
          if(e.sequence>this.seq+1){ws.close();return;}
        }
        if(e.sequence!=null)this.seq=e.sequence;
        if(e.event_id){this.seen.add(e.event_id);if(this.seen.size>3000)this.seen.delete(this.seen.values().next().value);}
        this.notify(e);
      };
      ws.onmessage=m=>{try{const e=JSON.parse(m.data);if(ready)receive(e);else if(queue.length<500)queue.push(e);else ws.close();}catch{ws.close();}};
      ws.onerror=()=>ws.close();ws.onclose=()=>{if(this.closed||ws!==this.ws)return;this.status('Disconnected');this.timer=setTimeout(()=>this.connect(),this.delay);this.delay=Math.min(15000,this.delay*2);};
    }
    stop(){this.closed=true;clearTimeout(this.timer);this.ws?.close();}
  }
  function demoRecord(write,value){
    return new Promise(resolve=>{
      const open=indexedDB.open('antropy-demo-fixtures',1);
      open.onupgradeneeded=()=>open.result.createObjectStore('scenario');
      open.onerror=()=>resolve(null);
      open.onsuccess=()=>{const db=open.result;const tx=db.transaction('scenario',write?'readwrite':'readonly');
        const store=tx.objectStore('scenario');const req=write?store.put(value,'gate'):store.get('gate');
        tx.oncomplete=()=>{db.close();resolve(req.result);};tx.onerror=()=>{db.close();resolve(null);};};
    });
  }
  return {demoSnapshot,Django,demoRecord};
})();
