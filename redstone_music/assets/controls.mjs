import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';

// Full-length operation uses bounded chunk windows for both maintenance and play.
export async function build({OUT,PACK,FN,info,blocks,notes,heads,resetRepeaters,lightModules}){
 const NS='nevada_full',OBJ='nv_full',N=info.bounds.length,SEG=256,segments=Math.ceil(N/SEG);
 const write=(name,lines)=>{const p=`${FN}/${name}.mcfunction`;fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,lines.join('\n')+'\n');};
 const set=b=>`setblock ${b.x} ${b.y} ${b.z} ${b.state}`;
 const snbt=v=>Array.isArray(v)?'['+v.map(snbt).join(',')+']':typeof v==='object'?'{'+Object.entries(v).map(([k,v])=>`${k}:${snbt(v)}`).join(',')+'}':typeof v==='boolean'?(v?'1b':'0b'):JSON.stringify(v);
 const place=b=>set(b)+(b.nbt?snbt(b.nbt):'');
 const fun=n=>`function ${NS}:${n}`;
 const sch=(n,t)=>`schedule function ${NS}:${n} ${t}t replace`;
 const say=s=>`execute unless entity @a run say NEVADA_FULL_${s}`;
 const text=(s,color='gold',who='@a')=>`tellraw ${who} ${JSON.stringify({text:s,color})}`;
 const camera='@e[type=minecraft:item_display,tag=nv_full_camera,limit=1]';
 const viewer='@a[tag=nv_full_view]';
 const noteState=(n,instrument=n.instrument)=>`minecraft:note_block[instrument=${instrument},note=${n.note},powered=false]`;
 const wire='minecraft:redstone_wire[power=0,north=none,south=none,east=none,west=none]';
 const release=[];
 for(let z=0;z<N;z+=768)release.push(`forceload remove 0 ${z} 79 ${Math.min(z+767,N-1)}`);
 write('release',release);
 const readyWindow=['function nevada_full:release','forceload add 0 0 79 191'];
 fs.mkdirSync(`${PACK}/data/minecraft/tags/function`,{recursive:true});
 for(const n of ['load','tick'])fs.writeFileSync(`${PACK}/data/minecraft/tags/function/${n}.json`,JSON.stringify({values:[`${NS}:${n}`]}));
 fs.writeFileSync(`${PACK}/pack.mcmeta`,JSON.stringify({pack:{pack_format:48,description:'Nevada 全曲红石音乐：实体红石演奏、三刻平滑跟拍、分段复位'}},null,2));
 write('load',[
  `scoreboard objectives add ${OBJ} dummy`,
  ...[['#voice',0,1,0],['#sustain',0,1,1],['#camDur',1,3,3]].map(([k,a,b,v])=>`execute unless score ${k} ${OBJ} matches ${a}..${b} run scoreboard players set ${k} ${OBJ} ${v}`),
  `scoreboard players operation #camLead ${OBJ} = #camDur ${OBJ}`,`scoreboard players remove #camLead ${OBJ} 1`,
  `scoreboard players set #sixteen ${OBJ} 16`,
  `execute unless score #built ${OBJ} matches 1 run ${fun('uninitialized')}`,
  `execute if score #built ${OBJ} matches 1 run ${fun('recover')}`]);
 write('uninitialized',[
  `scoreboard players set #busy ${OBJ} 1`,
  text('Nevada 数据包未绑定轨道。空白世界构建用 /function nevada_full:prepare；完整投影粘贴后用 /function nevada_full:adopt。','yellow')]);
 write('adopt',[`scoreboard players set #built ${OBJ} 1`,fun('recover')]);
 write('prepare',[`scoreboard players set #op ${OBJ} 1`,fun('maintenance/begin'),
  'gamerule doDaylightCycle false','gamerule doWeatherCycle false','gamerule doMobSpawning false','gamerule randomTickSpeed 0','gamerule spawnChunkRadius 0','time set midnight','setworldspawn 37 111 68']);
 write('recover',[`scoreboard players set #op ${OBJ} 0`,fun('maintenance/begin')]);
 write('stop',[say('STOP'),fun('recover')]);
 const breakLoaded=[];
 for(let z=0;z<N;z+=16)for(let x=0;x<80;x+=16)breakLoaded.push(`execute if loaded ${x+8} 110 ${z+8} run fill ${x} 88 ${z} ${x+15} 133 ${Math.min(z+15,N-1)} minecraft:air replace minecraft:repeater`);
 write('maintenance/break_loaded',breakLoaded);
 write('maintenance/begin',[
  `scoreboard players set #busy ${OBJ} 1`,
  ...['wait_start','launch','finish','off','maintenance/wait','maintenance/restore','maintenance/advance'].map(n=>`schedule clear ${NS}:${n}`),
  `execute as ${viewer} run spectate`,`gamemode creative ${viewer}`,`tag ${viewer} remove nv_full_view`,
  'kill @e[type=minecraft:item_display,tag=nv_full_camera]','stopsound @a record',
  fun('maintenance/break_loaded'),fun('release'),`scoreboard players set #seg ${OBJ} 0`,
  text('正在分段准备全曲轨道，完成后会显示“全曲就绪”。'),fun('maintenance/enter')]);
 const enter=[],restore=[],apply=[];
 const noteMap=new Map(notes.map(n=>[n.id,n]));
 for(let i=0;i<segments;i++){
  const lo=i*SEG,hi=Math.min(N-1,lo+SEG-1);
  enter.push(`execute if score #seg ${OBJ} matches ${i} run ${fun(`maintenance/enter_${i}`)}`);
  write(`maintenance/enter_${i}`,['function nevada_full:release',`forceload add 0 ${lo} 79 ${hi}`,sch('maintenance/wait',5)]);
  const checks=[];
  for(let x=0;x<80;x+=16)for(let z=lo;z<=hi;z+=16)checks.push(`execute unless loaded ${x+8} 110 ${z+8} run scoreboard players add #pending ${OBJ} 1`);
  write(`maintenance/check_${i}`,checks);
  const slice=blocks.filter(b=>b.z>=lo&&b.z<=hi).sort((a,b)=>(a.state.includes(':observer')?1:0)-(b.state.includes(':observer')?1:0)||a.y-b.y||a.z-b.z||a.x-b.x);
  const clear=[];for(let z=lo;z<=hi;z+=8)clear.push(`fill 0 88 ${z} 79 133 ${Math.min(z+7,hi)} minecraft:air`);
  write(`build/segment_${i}`,[...clear,...slice.map(place)]);
  const reps=resetRepeaters.filter(b=>b.z>=lo&&b.z<=hi);
  write(`maintenance/clear_${i}`,[...reps.map(b=>set({...b,state:'minecraft:air'})),...(i===0?[fun('off')]:[])]);
  write(`maintenance/restore_${i}`,[...reps.map(set),sch('maintenance/advance',i===0?40:2)]);
  restore.push(`execute if score #seg ${OBJ} matches ${i} run ${fun(`maintenance/restore_${i}`)}`);
  apply.push(`execute if score #seg ${OBJ} matches ${i} run ${fun(`maintenance/apply_${i}`)}`);
  const sliceNotes=notes.filter(n=>n.z>=lo&&n.z<=hi);
  const sliceLights=lightModules.filter(m=>m.z>=lo&&m.z<=hi&&m.events.every(id=>noteMap.get(id).kind==='retrigger'));
  for(const sustain of [0,1])for(const voice of [0,1]){
   const lines=[];
   for(const n of sliceNotes){
    const vocal=['voice','echo'].includes(n.family);
    if(vocal)lines.push(set({...n.base,state:voice?'minecraft:dirt':n.baseBlock}));
    lines.push(set({...n,state:!sustain&&n.kind==='retrigger'?'minecraft:air':noteState(n,vocal&&voice?'harp':n.instrument)}));
   }
   for(const m of sliceLights)lines.push(set({x:m.x,y:m.y-1,z:m.z,state:sustain?wire:'minecraft:air'}));
   write(`settings/segment_${i}_${sustain}_${voice}`,lines);
  }
  write(`maintenance/apply_${i}`, [
   `execute if score #op ${OBJ} matches 1 run ${fun(`build/segment_${i}`)}`,
   fun(`maintenance/clear_${i}`),
   ...[0,1].flatMap(s=>[0,1].map(v=>`execute if score #sustain ${OBJ} matches ${s} if score #voice ${OBJ} matches ${v} run ${fun(`settings/segment_${i}_${s}_${v}`)}`)),
   sch('maintenance/restore',20)]);
 }
 write('maintenance/enter',enter);
 write('maintenance/wait',[
  `scoreboard players set #pending ${OBJ} 0`,
  ...Array.from({length:segments},(_,i)=>`execute if score #seg ${OBJ} matches ${i} run ${fun(`maintenance/check_${i}`)}`),
  `execute if score #pending ${OBJ} matches 1.. run ${sch('maintenance/wait',5)}`,
  `execute if score #pending ${OBJ} matches 0 run ${fun('maintenance/apply')}`]);
 write('maintenance/apply',apply);write('maintenance/restore',restore);
 write('maintenance/advance',[
  `scoreboard players add #seg ${OBJ} 1`,
  `execute if score #seg ${OBJ} matches ..${segments-1} run ${fun('maintenance/enter')}`,
  `execute if score #seg ${OBJ} matches ${segments} run ${fun('ready')}`]);
 write('ready',[...readyWindow,`scoreboard players set #built ${OBJ} 1`,`scoreboard players set #busy ${OBJ} 0`,
  text('Nevada 全曲就绪。按“开始试听”，或输入 /function nevada_full:start。','green'),say('READY')]);
 write('start',[
  `execute if score #busy ${OBJ} matches 1.. run ${text('轨道正在准备或演奏，请等待“全曲就绪”。','yellow','@s')}`,
  `execute if score #busy ${OBJ} matches 0 run ${fun('countdown')}`]);
 write('countdown',[
  'tag @s add nv_full_view',`gamemode spectator ${viewer}`,'kill @e[type=minecraft:item_display,tag=nv_full_camera]',
  `execute store result storage ${NS}:camera duration int 1 run scoreboard players get #camDur ${OBJ}`,
  `${fun('camera/spawn')} with storage ${NS}:camera`,
  `tp ${viewer} 37.5 110.88 48.5 0 0`,`scoreboard players set #busy ${OBJ} 1`,...readyWindow,
  `title ${viewer} actionbar {"text":"准备开始 · Nevada 完整版"}`,sch('wait_start',10),
  `spectate ${camera} @a[tag=nv_full_view,limit=1]`]);
 write('camera/spawn',['$summon minecraft:item_display 37.5 112.5 48.5 {Tags:["nv_full_camera"],teleport_duration:$(duration),view_range:0f,shadow_radius:0f}']);
 const waitStart=[];for(let x=0;x<80;x+=16)for(let z=0;z<192;z+=16)waitStart.push(`execute unless loaded ${x+8} 110 ${z+8} run scoreboard players add #pending ${OBJ} 1`);
 write('wait_start',[`scoreboard players set #pending ${OBJ} 0`,...waitStart,
  `execute if score #pending ${OBJ} matches 1.. run ${sch('wait_start',10)}`,
  `execute if score #pending ${OBJ} matches 0 run ${sch('launch',1)}`]);
 write('launch',[
  `execute store result score #launch ${OBJ} run time query gametime`,
  `scoreboard players set #busy ${OBJ} 2`,`scoreboard players set #lastMin ${OBJ} 0`,
  ...heads.map(h=>set({...h,state:h.on})),sch('off',6),sch('finish',info.excerpt.musicGT+120),say('LAUNCH')]);
 write('off',heads.map(h=>set({...h,state:h.off})));
 write('tick',[`execute if score #busy ${OBJ} matches 2 run ${fun('follow')}`]);
 const maxMin=N/16-12;
 write('follow',[
  `execute store result score #q ${OBJ} run time query gametime`,`scoreboard players operation #q ${OBJ} -= #launch ${OBJ}`,
  `scoreboard players remove #q ${OBJ} 70`,`scoreboard players add #q ${OBJ} 1`,
  `scoreboard players operation #min ${OBJ} = #q ${OBJ}`,`scoreboard players add #min ${OBJ} 80`,
  `scoreboard players operation #min ${OBJ} /= #sixteen ${OBJ}`,`scoreboard players remove #min ${OBJ} 4`,
  `execute if score #min ${OBJ} matches ..-1 run scoreboard players set #min ${OBJ} 0`,
  `execute if score #min ${OBJ} matches ${maxMin+1}.. run scoreboard players set #min ${OBJ} ${maxMin}`,
  `execute unless score #min ${OBJ} = #lastMin ${OBJ} run ${fun('move_window')}`,
  `execute if score #q ${OBJ} matches -20..${info.excerpt.musicGT+20} run ${fun('position_camera')}`]);
 const dispatch=[];
 for(let i=1;i<=maxMin;i++){
  const z=(i+11)*16;
  write(`window/${i}`,[`forceload add 0 ${z} 79 ${z+15}`,`forceload remove 0 ${(i-1)*16} 79 ${i*16-1}`]);
  dispatch.push(`execute if score #min ${OBJ} matches ${i} run ${fun(`window/${i}`)}`);
 }
 write('move_window',[...dispatch,`scoreboard players operation #lastMin ${OBJ} = #min ${OBJ}`]);
 write('position_camera',[
  `scoreboard players operation #z ${OBJ} = #q ${OBJ}`,`scoreboard players operation #z ${OBJ} += #camLead ${OBJ}`,
  `scoreboard players operation #z ${OBJ} += #z ${OBJ}`,`scoreboard players add #z ${OBJ} 137`,
  `execute store result storage ${NS}:camera z double 0.5 run scoreboard players get #z ${OBJ}`,
  `${fun('camera/teleport')} with storage ${NS}:camera`]);
 write('camera/teleport',[`$tp ${camera} 37.5 112.5 $(z) 0 0`]);
 write('finish',[say('FINISHED'),text('Nevada 全曲结束，正在复位轨道。','green'),fun('recover')]);
 for(const [name,player,value]of [['voice_harp','#voice',1],['voice_flute','#voice',0],['sustain','#sustain',1],['dry','#sustain',0]]){
  write(name,[`execute if score #busy ${OBJ} matches 0 run ${fun(`settings/request_${name}`)}`]);
  write(`settings/request_${name}`,[`scoreboard players set ${player} ${OBJ} ${value}`,fun('recover')]);
 }
 for(const d of [1,2,3]){
  write(`camera/buffer${d}`,[`execute if score #busy ${OBJ} matches 0 run ${fun(`camera/set${d}`)}`]);
  write(`camera/set${d}`,[`scoreboard players set #camDur ${OBJ} ${d}`,`scoreboard players set #camLead ${OBJ} ${d-1}`,text(`相机已设为 ${d} 刻缓冲。`,'aqua','@s')]);
 }
 write('validate_start',[fun('countdown')]);
 if(info.version.startsWith('fx_')){
  // Track the empty display before binding: avoids a camera packet arriving
  // before its spawn packet on a clean vanilla client.
  const spawnPath=`${FN}/camera/spawn.mcfunction`;
  fs.writeFileSync(spawnPath,fs.readFileSync(spawnPath,'utf8').replace('view_range:0f','view_range:1f'));
  const countdownPath=`${FN}/countdown.mcfunction`;
  fs.writeFileSync(countdownPath,fs.readFileSync(countdownPath,'utf8').replace(`spectate ${camera} @a[tag=nv_full_view,limit=1]`,sch('camera/bind',2)));
  write('camera/bind',[`execute if score #busy ${OBJ} matches 1.. run spectate ${camera} @a[tag=nv_full_view,limit=1]`]);
  fs.appendFileSync(`${FN}/maintenance/begin.mcfunction`,`schedule clear ${NS}:camera/bind\n`);
  for(const [name,value]of [['fx_on',1],['fx_off',0]])write(name,[`execute if score #busy ${OBJ} matches 0 run scoreboard players set #fx ${OBJ} ${value}`,text(value?'粒子已开启。':'粒子已关闭。','aqua','@s')]);
  write('p3_defaults',[`scoreboard players set #voice ${OBJ} 0`,`scoreboard players set #sustain ${OBJ} 1`,`scoreboard players set #camDur ${OBJ} 3`,`scoreboard players set #camLead ${OBJ} 2`,fun('recover')]);
  write('fx_state',[
   `execute store result storage nevada_full:fx playing int 1 run scoreboard players get #busy ${OBJ}`,
   `execute store result storage nevada_full:fx enabled int 1 run scoreboard players get #fx ${OBJ}`,
   `execute store result storage nevada_full:fx q int 1 run scoreboard players get #q ${OBJ}`,
   `execute store result storage nevada_full:fx run int 1 run scoreboard players get #run ${OBJ}`,
   `data modify storage nevada_full:fx sample set value ${info.fxSample?.key??0}`]);
  const append=(n,t)=>fs.appendFileSync(`${FN}/${n}.mcfunction`,t+'\n');
  append('load',`execute unless score #fx ${OBJ} matches 0..1 run scoreboard players set #fx ${OBJ} 1`);
  append('launch',`scoreboard players set #q ${OBJ} -70`);
  append('launch',`scoreboard players add #run ${OBJ} 1`);
  append('tick',fun('fx_state'));
  if(info.fxSample?.id!=='full')for(const p of fs.readdirSync(FN,{recursive:true}).filter(p=>p.endsWith('.mcfunction'))){const f=`${FN}/${p}`;fs.writeFileSync(f,fs.readFileSync(f,'utf8').replaceAll('全曲','样段').replaceAll('完整版',`${info.excerpt.seconds}秒粒子样段${info.fxSample?' · '+info.fxSample.label:''}`));}
 }
 const registry=new Set(fs.readdirSync(FN,{recursive:true}).filter(p=>p.endsWith('.mcfunction')).map(p=>p.replaceAll('\\','/').replace(/\.mcfunction$/,'')));
 for(const n of registry){const t=fs.readFileSync(`${FN}/${n}.mcfunction`,'utf8');for(const m of t.matchAll(/\bfunction nevada_full:([a-z0-9_/]+)/g))assert(registry.has(m[1]),m[1]);assert(!/^\s*playsound\b/m.test(t));}
 fs.writeFileSync(`${OUT}/maintenance_plan.json`,JSON.stringify({segmentLength:SEG,segments,maxMaintenanceChunks:80,playbackChunks:60,maxForceloadDuringWindowShift:65,allMusicPhysicalRedstone:true,resetRepeaters:resetRepeaters.length,heads:heads.length},null,2));
}

// Public configurable adapter. Template-local identifiers are rewritten atomically
// before the pack is exposed; each project owns a unique namespace and scoreboard.
export async function buildConfigured(options, namespace, objective, title) {
 await build(options);
 for(const rel of fs.readdirSync(options.PACK,{recursive:true})) {
  const p=path.join(options.PACK,rel);
  if(!fs.statSync(p).isFile()) continue;
  const text=fs.readFileSync(p,'utf8').replaceAll('nevada_full',namespace).replaceAll('nv_full',objective).replaceAll('Nevada',JSON.stringify(title).slice(1,-1));
  fs.writeFileSync(p,text);
 }
}
if(process.argv[2]) {
 const data=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
 await buildConfigured(data,data.info.namespace,data.info.objective,data.info.title.replace(/[\r\n]/g,' '));
}
