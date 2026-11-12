const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn,spawnSync} = require('node:child_process');
const test = require('node:test');
const installer = path.resolve(__dirname, '../install-crons.js');

function setup(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'egbe-cron-'));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  const bin = path.join(root,'bin'); fs.mkdirSync(bin);
  const run = path.join(root,"run with 'quote%percent"); fs.mkdirSync(run);
  const store = path.join(root,'crontab');
  fs.writeFileSync(store,'# unrelated\n0 0 * * * echo keep\n');
  fs.writeFileSync(path.join(bin,'crontab'), `#!${process.execPath}
const fs=require('fs');
if(process.argv[2]==='-l') process.stdout.write(fs.readFileSync(process.env.CRON_TEST_STORE,'utf8'));
else {
  const table=fs.readFileSync(0,'utf8');
  fs.writeFileSync(process.env.CRON_TEST_STORE,table);
  if(process.env.CRON_TEST_DAEMON!=='stopped') {
    for(const line of table.split('\\n')) {
      if(line.includes('# EGBE-INSTANTLY-PROBE-')) {
        const command=line.slice('* * * * * '.length).split(' # EGBE-INSTANTLY-PROBE-')[0].replace(/\\\\%/g,'%');
        require('child_process').execFileSync('/bin/sh',['-c',command]);
      }
    }
  }
}
`,{mode:0o755});
  fs.writeFileSync(path.join(bin,'which'), `#!${process.execPath}
const fs=require('fs'),p=require('path').join(${JSON.stringify(bin)},process.argv[2]);
if(fs.existsSync(p)) console.log(p); else process.exit(1);
`,{mode:0o755});
  fs.writeFileSync(path.join(run,'manifest.json'),JSON.stringify({run_key:'audit',campaign:{id:'synthetic'}}));
  fs.writeFileSync(path.join(run,'run-spec.json'),JSON.stringify({lead_replenishment:{enabled:true},monitoring:{snapshot_schedule:'30 9 * * *'}}));
  fs.writeFileSync(path.join(run,'.env'),'OS_URL=https://invalid.example\nOS_API_KEY=dummy-offline-only\n',{mode:0o600});
  // Accelerate only the stopped-daemon fixture's polling clock. Production
  // still requires a full minute plus startup margin; no short timeout bypass.
  const clock=path.join(root,'cron-clock.cjs');
  fs.writeFileSync(clock,`if(process.env.CRON_TEST_DAEMON==='stopped') {
    let now=Date.now(); const original=setTimeout;
    Date.now=()=>now;
    global.setTimeout=(callback,delay,...args)=>{now+=delay;return original(callback,0,...args);};
  }`);
  const env={...process.env,PATH:bin,CRON_TEST_STORE:store,EGBE_CRON_LOCK_DIR:path.join(root,'installer.lock'),
    NODE_OPTIONS:(process.env.NODE_OPTIONS || '')+' --require '+JSON.stringify(clock)};
  const execute = (...extra)=>spawnSync(process.execPath,[installer,'--run-dir',run,'--scheduler','cron',...extra],
    {encoding:'utf8',env});
  return {root,run,store,execute,env};
}

test('direct cron installs all jobs without OpenClaw, preserves other entries and reruns idempotently',t=>{
  const {run,store,execute}=setup(t);
  let result=execute('--check-scheduler'); assert.equal(result.status,0,result.stderr);
  assert.equal(JSON.parse(result.stdout).available,true);
  result=execute(); assert.equal(result.status,0,result.stderr);
  let receipt=JSON.parse(fs.readFileSync(path.join(run,'cron-install.json')));
  assert.equal(receipt.installed,true); assert.equal(receipt.scheduler,'cron');
  assert.deepEqual(receipt.jobs.map(x=>x.key),['reply','monitor','replenish','conclude']);
  const first=fs.readFileSync(store,'utf8');
  assert.ok(first.includes('# unrelated\n0 0 * * * echo keep\n'));
  assert.ok(first.includes('\\%')); assert.ok(first.includes('run-cron-job.js'));
  assert.ok(!first.includes('dummy-offline-only'));
  result=execute(); assert.equal(result.status,0,result.stderr);
  assert.equal(fs.readFileSync(store,'utf8'),first);
  fs.writeFileSync(path.join(run,'run-spec.json'),JSON.stringify({lead_replenishment:{enabled:false}}));
  result=execute(); assert.equal(result.status,0,result.stderr);
  assert.equal((fs.readFileSync(store,'utf8').match(/run-cron-job.js/g)||[]).length,2);
});

test('changing schedulers leaves prior successful installation intact',t=>{
  const {run,execute}=setup(t);
  const prior=JSON.stringify({installed:true,scheduler:'openclaw',jobs:[{id:'keep'}]});
  fs.writeFileSync(path.join(run,'cron-install.json'),prior);
  const result=execute(); assert.notEqual(result.status,0);
  assert.match(result.stderr,/before switching schedulers/);
  assert.equal(fs.readFileSync(path.join(run,'cron-install.json'),'utf8'),prior);
});

test('optional snapshot schedule cannot inject commands or another cron entry', t=>{
  const {run,store,execute}=setup(t);
  const before=fs.readFileSync(store,'utf8');
  for(const schedule of ['* * * * * command', '* * * * *\n* * * * * command']) {
    fs.writeFileSync(path.join(run,'run-spec.json'), JSON.stringify({monitoring:{snapshot_schedule:schedule}}));
    const result=execute();
    assert.notEqual(result.status,0);
    assert.match(result.stderr,/five numeric cron fields/);
    assert.equal(fs.readFileSync(store,'utf8'),before);
  }
});

test('missing OpenClaw still writes a manual runbook and cannot claim completion',t=>{
  const {run,execute}=setup(t);
  const result=execute('--scheduler','openclaw'); assert.notEqual(result.status,0);
  const receipt=JSON.parse(fs.readFileSync(path.join(run,'cron-install.json')));
  assert.equal(receipt.installed,false); assert.equal(receipt.manual_monitoring.length,4);
});

test('direct ticks run a script once, refuse overlap and release locks after failures',t=>{
  const {root,run}=setup(t);
  const scripts=path.join(root,'scripts'); fs.mkdirSync(scripts);
  fs.cpSync(path.join(__dirname,'../run-cron-job.js'),path.join(scripts,'run-cron-job.js'));
  fs.mkdirSync(path.join(scripts,'lib')); fs.copyFileSync(path.join(__dirname,'helpers.js'),path.join(scripts,'lib/helpers.js'));
  fs.writeFileSync(path.join(scripts,'monitor-campaign.js'),'process.exit(7)');
  const args=[path.join(scripts,'run-cron-job.js'),'--job','monitor','--run-dir',run,
    '--env-file',path.join(run,'.env'),'--timeout-seconds','1'];
  let result=spawnSync(process.execPath,args,{encoding:'utf8'}); assert.equal(result.status,7,result.stderr);
  const lock=path.join(run,'.cron-monitor.lock'); assert.equal(fs.existsSync(lock),false);
  fs.mkdirSync(lock); result=spawnSync(process.execPath,args,{encoding:'utf8'});
  assert.notEqual(result.status,0); assert.match(result.stderr,/Concurrent or stale job lock/);
  fs.rmSync(lock,{recursive:true});
  fs.writeFileSync(path.join(scripts,'monitor-campaign.js'),'setTimeout(()=>{},10000)');
  result=spawnSync(process.execPath,args,{encoding:'utf8'}); assert.notEqual(result.status,0);
  assert.equal(fs.existsSync(lock),false);
});


test('failed cron readback cannot record a successful installation',t=>{
  const {root,run,execute}=setup(t);
  const mock=path.join(root,'bin/crontab');
  const original=fs.readFileSync(mock,'utf8');
  // The daemon executes the probe, but the client loses the campaign block.
  fs.writeFileSync(mock,original.replace("fs.writeFileSync(process.env.CRON_TEST_STORE,table);",
    "fs.writeFileSync(process.env.CRON_TEST_STORE,table.includes('# BEGIN EGBE-INSTANTLY-') ? '# unrelated\\n' : table);"));
  const result=execute(); assert.notEqual(result.status,0);
  assert.match(result.stderr,/verification failed/);
  assert.equal(fs.existsSync(path.join(run,'cron-install.json')),false);
});


test('verified cleanup records removal and allows a replacement scheduler',t=>{
  const {root,run,store,execute}=setup(t);
  let result=execute(); assert.equal(result.status,0,result.stderr);
  result=execute('--remove'); assert.equal(result.status,0,result.stderr);
  assert.equal(fs.readFileSync(store,'utf8'),'# unrelated\n0 0 * * * echo keep\n');
  const receipt=JSON.parse(fs.readFileSync(path.join(run,'cron-install.json')));
  assert.equal(receipt.installed,false); assert.ok(receipt.removed_at);
  // OpenClaw remains absent, but switching is now permitted and reaches its
  // normal manual fallback instead of rejecting the old successful receipt.
  result=execute('--scheduler','openclaw');
  assert.notEqual(result.status,0);
  assert.doesNotMatch(result.stderr,/before switching schedulers/);
  assert.match(result.stderr,/Manual monitoring fallback/);
});

test('concurrent campaign installers cannot erase a successful run block',async t=>{
  const {root,run,store,env,execute}=setup(t);
  const other=path.join(root,'other-run'); fs.cpSync(run,other,{recursive:true});
  const manifest=JSON.parse(fs.readFileSync(path.join(other,'manifest.json')));
  manifest.run_key='other'; fs.writeFileSync(path.join(other,'manifest.json'),JSON.stringify(manifest));
  const mock=path.join(root,'bin/crontab');
  const source=fs.readFileSync(mock,'utf8');
  fs.writeFileSync(mock,source.replace("const fs=require('fs');", "const fs=require('fs'); Atomics.wait(new Int32Array(new SharedArrayBuffer(4)),0,0,250);"));
  const install=dir=>new Promise(resolve=>{
    const child=spawn(process.execPath,[installer,'--run-dir',dir,'--scheduler','cron'],{env,stdio:'pipe'});
    let stderr=''; child.stderr.on('data',chunk=>stderr+=chunk);
    child.on('close',status=>resolve({status,stderr}));
  });
  const results=await Promise.all([install(run),install(other)]);
  assert.equal(results.filter(x=>x.status===0).length,1);
  assert.match(results.find(x=>x.status!==0).stderr,/installer lock exists/);
  const result=execute('--run-dir',results[0].status===0 ? other : run);
  assert.equal(result.status,0,result.stderr);
  assert.equal((fs.readFileSync(store,'utf8').match(/# BEGIN EGBE-INSTANTLY/g)||[]).length,2);
});


test('cleanup uses the persisted marker from a prior symlink-path installation',t=>{
  const {root,run,store,execute}=setup(t);
  const alias=path.join(root,'run-alias'); fs.symlinkSync(run,alias);
  let result=execute('--run-dir',alias); assert.equal(result.status,0,result.stderr);
  const receiptPath=path.join(run,'cron-install.json');
  const receipt=JSON.parse(fs.readFileSync(receiptPath));
  // Simulate an installation from the earlier lexical-path implementation.
  const oldMarker='EGBE-INSTANTLY-'+require('crypto').createHash('sha256').update(alias).digest('hex').slice(0,24);
  fs.writeFileSync(store,fs.readFileSync(store,'utf8').replaceAll(receipt.marker,oldMarker));
  receipt.marker=oldMarker; fs.writeFileSync(receiptPath,JSON.stringify(receipt));
  result=execute('--remove'); assert.equal(result.status,0,result.stderr);
  assert.equal(fs.readFileSync(store,'utf8'),'# unrelated\n0 0 * * * echo keep\n');
  assert.equal(JSON.parse(fs.readFileSync(receiptPath)).installed,false);
});


test('malformed cron blocks cannot produce a successful removal receipt',t=>{
  const {run,store,execute}=setup(t);
  let result=execute(); assert.equal(result.status,0,result.stderr);
  const priorReceipt=fs.readFileSync(path.join(run,'cron-install.json'),'utf8');
  const malformed=fs.readFileSync(store,'utf8').replace(/^# BEGIN EGBE-INSTANTLY.*\n/m,'');
  fs.writeFileSync(store,malformed);
  result=execute('--remove'); assert.notEqual(result.status,0);
  assert.match(result.stderr,/recorded entries remain/);
  assert.equal(fs.readFileSync(store,'utf8'),malformed);
  assert.equal(fs.readFileSync(path.join(run,'cron-install.json'),'utf8'),priorReceipt);
});

test('OpenClaw cleanup removes renamed jobs by recorded stable IDs',t=>{
  const {root,run,execute}=setup(t);
  const jobStore=path.join(root,'openclaw-jobs.json');
  const quote=value=>`'${String(value).replace(/'/g, `'\\''`)}'`;
  fs.writeFileSync(jobStore,JSON.stringify([{id:'stable-123',name:'renamed-by-operator',
    payload:{message:`  cd '/skill/scripts' && node monitor-campaign.js --run-dir ${quote(fs.realpathSync(run))} --env-file ${quote(path.join(run,'.env'))}`}}]));
  fs.writeFileSync(path.join(root,'bin/openclaw'),`#!${process.execPath}
const fs=require('fs'),store=${JSON.stringify(jobStore)};
const jobs=JSON.parse(fs.readFileSync(store));
if(process.argv[3]==='list') console.log(JSON.stringify(jobs));
else if(process.argv[3]==='remove') fs.writeFileSync(store,JSON.stringify(jobs.filter(job=>job.id!==process.argv[4])));
`,{mode:0o755});
  fs.writeFileSync(path.join(run,'cron-install.json'),JSON.stringify({installed:true,scheduler:'openclaw',
    jobs:[{name:'instantly-audit-monitor',ids:['stable-123']}]}));
  fs.writeFileSync(path.join(run,'manifest.json'),'{truncated');
  const result=execute('--scheduler','openclaw','--remove'); assert.equal(result.status,0,result.stderr);
  assert.deepEqual(JSON.parse(fs.readFileSync(jobStore)),[]);
  assert.equal(JSON.parse(fs.readFileSync(path.join(run,'cron-install.json'))).installed,false);
});


test('reinstall rejects orphaned cron entries when both boundary markers are gone',t=>{
  const {run,store,execute}=setup(t);
  let result=execute(); assert.equal(result.status,0,result.stderr);
  const receipt=fs.readFileSync(path.join(run,'cron-install.json'),'utf8');
  const orphaned=fs.readFileSync(store,'utf8').replace(/^# (?:BEGIN|END) EGBE-INSTANTLY.*\n/gm,'');
  fs.writeFileSync(store,orphaned);
  result=execute(); assert.notEqual(result.status,0);
  assert.match(result.stderr,/orphaned recorded entries/);
  assert.equal(fs.readFileSync(store,'utf8'),orphaned);
  assert.equal(fs.readFileSync(path.join(run,'cron-install.json'),'utf8'),receipt);
});

test('preflight and install reject an inert crontab and clean up the execution probe',t=>{
  const {run,store,execute,env}=setup(t);
  const prior=fs.readFileSync(store,'utf8');
  env.CRON_TEST_DAEMON='stopped';
  for(const args of [['--check-scheduler'],[]]) {
    const result=execute(...args); assert.notEqual(result.status,0);
    assert.match(result.stderr,/Cron execution probe timed out/);
    assert.equal(fs.readFileSync(store,'utf8'),prior);
    assert.equal(fs.existsSync(path.join(run,'cron-install.json')),false);
  }
});


test('probe timeout cannot be shorter than a full cron interval',t=>{
  const {store,execute}=setup(t);
  const prior=fs.readFileSync(store,'utf8');
  const result=execute('--check-scheduler','--scheduler-check-timeout-seconds','59');
  assert.notEqual(result.status,0);
  assert.match(result.stderr,/integer from 65 to 120/);
  assert.equal(fs.readFileSync(store,'utf8'),prior);
});


test('cron cleanup works when the campaign manifest is missing or damaged',t=>{
  const {run,store,execute}=setup(t);
  const manifestPath=path.join(run,'manifest.json');
  const manifest=fs.readFileSync(manifestPath);
  for(const damaged of [null,'{truncated',JSON.stringify({run_key:'audit'})]) {
    fs.writeFileSync(manifestPath,manifest);
    let result=execute(); assert.equal(result.status,0,result.stderr);
    if(damaged===null) fs.unlinkSync(manifestPath);
    else fs.writeFileSync(manifestPath,damaged);
    result=execute('--remove'); assert.equal(result.status,0,result.stderr);
    assert.equal(fs.readFileSync(store,'utf8'),'# unrelated\n0 0 * * * echo keep\n');
    assert.equal(JSON.parse(fs.readFileSync(path.join(run,'cron-install.json'))).installed,false);
  }
});

// --- OpenClaw scheduler: delivery target, silent rule, send window ---------

// Real `openclaw agents list --json` output (OpenClaw 2026.10.2, fina-agent-01,
// user agent, 2026-10-20). Each project there has its own OpenClaw install.
const REAL_AGENTS_LIST = [{
  id:'fina',name:'fina',identityName:'fina',identitySource:'config',
  workspace:'/home/agent/.openclaw/workspace',agentDir:'/home/agent/.openclaw/agents/fina/agent',
  model:'custom-os-hz-egbe-dev/claude-sonnet-5.5',bindings:0,isDefault:true,
  createdVia:'operator',creatorAgentId:null,createdAt:1791852358902,
}];

// agents: the JSON `openclaw agents list --json` prints, or 'fail' to exit 1.
function mockOpenclaw(root, agents=REAL_AGENTS_LIST) {
  const jobStore = path.join(root,'openclaw-jobs.json');
  const callLog = path.join(root,'openclaw-calls.json');
  fs.writeFileSync(jobStore,'[]'); fs.writeFileSync(callLog,'[]');
  fs.writeFileSync(path.join(root,'bin/openclaw'),`#!${process.execPath}
const fs=require('fs'),store=${JSON.stringify(jobStore)},log=${JSON.stringify(callLog)};
const argv=process.argv.slice(2); const jobs=JSON.parse(fs.readFileSync(store));
fs.writeFileSync(log,JSON.stringify([...JSON.parse(fs.readFileSync(log)),argv]));
const value=flag=>argv[argv.indexOf(flag)+1];
if(argv[0]==='agents') {
  if(${JSON.stringify(agents)}==='fail') { console.error('gateway token mismatch'); process.exit(1); }
  console.log(${JSON.stringify(JSON.stringify(agents))});
}
else if(argv[1]==='list') {
  if(process.env.OPENCLAW_TEST_LIST_FAIL==='yes') { console.error('read failed'); process.exit(1); }
  console.log(JSON.stringify(jobs));
}
else if(argv[1]==='add') { const id='job-'+(Math.max(0,...jobs.map(job=>Number(job.id.replace(/^job-/,''))||0))+1);
  jobs.push({id,name:value('--name'),payload:{kind:'agentTurn',message:value('--message')}});
  fs.writeFileSync(store,JSON.stringify(jobs)); console.log(JSON.stringify({id})); }
else if(argv[1]==='edit') {
  const job=jobs.find(job=>job.id===argv[2]);
  if(!job) process.exit(1);
  job.name=value('--name'); job.payload={kind:'agentTurn',message:value('--message')};
  fs.writeFileSync(store,JSON.stringify(jobs));
}
else if(argv[1]==='remove') {
  if(process.env.OPENCLAW_TEST_REMOVE==='fail') { console.error('remove failed'); process.exit(1); }
  if(process.env.OPENCLAW_TEST_REMOVE!=='ignore') fs.writeFileSync(store,JSON.stringify(jobs.filter(job=>job.id!==argv[2])));
}
`,{mode:0o755});
  const calls = verb => JSON.parse(fs.readFileSync(callLog)).filter(argv=>argv[0]==='cron' && argv[1]===verb);
  const jobArgs = (verb,key) => calls(verb).find(argv=>argv[argv.indexOf('--name')+1].endsWith('-'+key));
  return {calls,jobArgs,jobStore};
}

test('OpenClaw reinstall removes omitted jobs, including renamed recorded jobs',t=>{
  const {root,run,execute}=setup(t);
  const {calls,jobStore}=mockOpenclaw(root);
  let result=execute('--scheduler','openclaw','--no-chat-delivery');
  assert.equal(result.status,0,result.stderr);
  const original=JSON.parse(fs.readFileSync(jobStore));
  const removedIds=original.filter(job=>/-(conclude|replenish)$/.test(job.name)).map(job=>job.id);
  original.find(job=>job.name.endsWith('-conclude')).name='renamed-export';
  fs.writeFileSync(jobStore,JSON.stringify(original));
  fs.writeFileSync(path.join(run,'run-spec.json'),'{}');
  result=execute('--scheduler','openclaw','--no-chat-delivery');
  assert.equal(result.status,0,result.stderr);
  assert.deepEqual(calls('remove').map(argv=>argv[2]).sort(),removedIds.sort());
  assert.deepEqual(JSON.parse(fs.readFileSync(jobStore)).map(job=>job.name).sort(),
    ['instantly-audit-monitor','instantly-audit-reply']);
  const receipt=JSON.parse(fs.readFileSync(path.join(run,'cron-install.json')));
  assert.deepEqual(receipt.jobs.map(job=>job.key),['reply','monitor']);
  assert.equal(receipt.verification.ok,true);
  result=execute('--scheduler','openclaw','--no-chat-delivery');
  assert.equal(result.status,0,result.stderr);
  assert.equal(calls('remove').length,2);
  assert.equal(calls('add').length,4);
});

test('OpenClaw reconcile and removal preserve another workspace with the same run key',t=>{
  const {root,run,execute}=setup(t);
  const {calls,jobStore}=mockOpenclaw(root);
  let result=execute('--scheduler','openclaw','--no-chat-delivery');
  assert.equal(result.status,0,result.stderr);
  const own=JSON.parse(fs.readFileSync(jobStore));
  const quote=value=>`'${String(value).replace(/'/g, `'\\''`)}'`;
  const foreign=own.map(job=>({...job,id:'foreign-'+job.id,
    payload:{...job.payload,message:job.payload.message.replaceAll(quote(fs.realpathSync(run)),quote(fs.realpathSync(run)+'-other'))}}));
  fs.writeFileSync(jobStore,JSON.stringify([...foreign,...own]));
  fs.writeFileSync(path.join(run,'run-spec.json'),'{}');
  result=execute('--scheduler','openclaw','--no-chat-delivery');
  assert.equal(result.status,0,result.stderr);
  let actual=JSON.parse(fs.readFileSync(jobStore));
  assert.deepEqual(actual.filter(job=>job.id.startsWith('foreign-')),foreign);
  assert.equal(actual.length,6);
  assert.ok(calls('edit').every(argv=>!argv[2].startsWith('foreign-')));
  assert.ok(calls('remove').every(argv=>!argv[2].startsWith('foreign-')));
  result=execute('--scheduler','openclaw','--remove');
  assert.equal(result.status,0,result.stderr);
  assert.deepEqual(JSON.parse(fs.readFileSync(jobStore)),foreign);
});

for(const failure of ['fail','ignore']) test(`OpenClaw omission removal (${failure}) preserves recovery receipts`,t=>{
  const {root,run,execute,env}=setup(t);
  mockOpenclaw(root);
  let result=execute('--scheduler','openclaw','--no-chat-delivery');
  assert.equal(result.status,0,result.stderr);
  const receipt=fs.readFileSync(path.join(run,'cron-install.json'),'utf8');
  const manifest=fs.readFileSync(path.join(run,'manifest.json'),'utf8');
  fs.writeFileSync(path.join(run,'run-spec.json'),'{}');
  env.OPENCLAW_TEST_REMOVE=failure;
  result=execute('--scheduler','openclaw','--no-chat-delivery');
  assert.notEqual(result.status,0);
  assert.equal(fs.readFileSync(path.join(run,'cron-install.json'),'utf8'),receipt);
  assert.equal(fs.readFileSync(path.join(run,'manifest.json'),'utf8'),manifest);
  delete env.OPENCLAW_TEST_REMOVE;
  result=execute('--scheduler','openclaw','--no-chat-delivery');
  assert.equal(result.status,0,result.stderr);
});

test('OpenClaw uncertain list or recorded job scope cannot mutate jobs or replace receipts',t=>{
  const {root,run,execute,env}=setup(t);
  const {calls,jobStore}=mockOpenclaw(root);
  let result=execute('--scheduler','openclaw','--no-chat-delivery');
  assert.equal(result.status,0,result.stderr);
  const receipt=fs.readFileSync(path.join(run,'cron-install.json'),'utf8');
  const jobs=JSON.parse(fs.readFileSync(jobStore));
  fs.writeFileSync(path.join(run,'run-spec.json'),'{}');
  env.OPENCLAW_TEST_LIST_FAIL='yes';
  result=execute('--scheduler','openclaw','--no-chat-delivery');
  assert.notEqual(result.status,0);
  delete env.OPENCLAW_TEST_LIST_FAIL;
  delete jobs.find(job=>job.name.endsWith('-conclude')).payload;
  fs.writeFileSync(jobStore,JSON.stringify(jobs));
  result=execute('--scheduler','openclaw','--no-chat-delivery');
  assert.notEqual(result.status,0);
  assert.match(result.stderr,/Cannot verify recorded OpenClaw job/);
  assert.equal(calls('remove').length,0);
  assert.equal(calls('edit').length,0);
  assert.equal(calls('add').length,4);
  assert.equal(fs.readFileSync(path.join(run,'cron-install.json'),'utf8'),receipt);
});

const DUBAI_SPEC = {lead_replenishment:{enabled:true},monitoring:{snapshot_schedule:'30 9 * * *'},campaign:{open_tracking:false,schedule:{
  name:'Weekdays',timing:{from:'09:00',to:'17:00'},timezone:'Asia/Dubai',
  days:{monday:true,tuesday:true,wednesday:true,thursday:true,friday:true,saturday:false,sunday:false}}}};

function flagValue(argv, flag) { const i=argv.indexOf(flag); return i<0 ? undefined : argv[i+1]; }

test('OpenClaw install passes the delivery target, the silent rule and the send window',t=>{
  const {root,run,execute}=setup(t);
  const {calls,jobArgs}=mockOpenclaw(root);
  fs.writeFileSync(path.join(run,'run-spec.json'),JSON.stringify(DUBAI_SPEC));
  const result=execute('--scheduler','openclaw','--deliver-channel','slack','--deliver-to','channel:C0C8VL12XNJ');
  assert.equal(result.status,0,result.stderr);
  assert.equal(calls('add').length,4);
  for(const argv of calls('add')) {
    assert.equal(flagValue(argv,'--agent'),'fina');
    assert.equal(flagValue(argv,'--channel'),'slack');
    assert.equal(flagValue(argv,'--to'),'channel:C0C8VL12XNJ');
    assert.ok(argv.includes('--announce')); assert.ok(!argv.includes('--no-deliver'));
    const message=flagValue(argv,'--message');
    assert.match(message.trim().split('\n').pop(),/must be exactly NO_REPLY/);
  }
  assert.equal(flagValue(jobArgs('add','reply'),'--cron'),'5 8-19 * * 1-5');
  assert.equal(flagValue(jobArgs('add','reply'),'--tz'),'Asia/Dubai');
  assert.equal(flagValue(jobArgs('add','monitor'),'--cron'),'15 8-19 * * 1-5');
  assert.equal(flagValue(jobArgs('add','monitor'),'--tz'),'Asia/Dubai');
  assert.match(flagValue(jobArgs('add','monitor'),'--message'),/"alert" is "new"/);
  assert.match(flagValue(jobArgs('add','monitor'),'--message'),/"pause_failed" is true/);
  assert.match(flagValue(jobArgs('add','replenish'),'--message'),/"leads_rejected_names" > 0, that is news/);
  assert.match(flagValue(jobArgs('add','replenish'),'--message'),/rejected-leads\.json/);
  assert.equal(flagValue(jobArgs('add','conclude'),'--cron'),'30 9 * * *');
  assert.equal(flagValue(jobArgs('add','conclude'),'--tz'),'UTC');
  assert.equal(flagValue(jobArgs('add','replenish'),'--cron'),'45 */2 * * *');
  const receipt=JSON.parse(fs.readFileSync(path.join(run,'cron-install.json')));
  assert.equal(receipt.installed,true); assert.equal(receipt.scheduler,'openclaw');
  assert.deepEqual({mode:receipt.delivery.mode,channel:receipt.delivery.channel,to:receipt.delivery.to},
    {mode:'announce',channel:'slack',to:'channel:C0C8VL12XNJ'});
  assert.equal(receipt.send_window.applied,true);
  assert.equal(receipt.send_window.reply,'5 8-19 * * 1-5');
  assert.equal(receipt.send_window.monitor,'15 8-19 * * 1-5');
  assert.deepEqual(receipt.jobs.find(j=>j.key==='reply').tz,'Asia/Dubai');
  // Rerun edits the same jobs, with the same delivery flags.
  const again=execute('--scheduler','openclaw','--deliver-channel','slack','--deliver-to','channel:C0C8VL12XNJ');
  assert.equal(again.status,0,again.stderr);
  assert.equal(calls('add').length,4); assert.equal(calls('edit').length,4);
  for(const argv of calls('edit')) {
    assert.equal(flagValue(argv,'--to'),'channel:C0C8VL12XNJ');
    assert.equal(flagValue(argv,'--agent'),'fina');
  }
  assert.deepEqual(receipt.agent,{id:'fina',source:'openclaw default agent'});
});

test('OpenClaw agent: --agent wins over the host default',t=>{
  const {root,run,execute}=setup(t);
  const {calls}=mockOpenclaw(root,[{id:'fina',isDefault:true},{id:'agbis'}]);
  const result=execute('--scheduler','openclaw','--no-chat-delivery','--agent','agbis');
  assert.equal(result.status,0,result.stderr);
  for(const argv of calls('add')) assert.equal(flagValue(argv,'--agent'),'agbis');
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(run,'cron-install.json'))).agent,{id:'agbis',source:'--agent'});
});

test('OpenClaw agent: the agent whose workspace holds the run dir wins over the default',t=>{
  const {root,run,execute}=setup(t);
  const {calls}=mockOpenclaw(root,[
    {id:'fina',isDefault:true,workspace:path.join(root,'fina-ws')},
    {id:'agbis',workspace:root},
  ]);
  const result=execute('--scheduler','openclaw','--no-chat-delivery'); assert.equal(result.status,0,result.stderr);
  for(const argv of calls('add')) assert.equal(flagValue(argv,'--agent'),'agbis');
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(run,'cron-install.json'))).agent,{id:'agbis',source:'run-dir workspace'});
});

test('OpenClaw agent: an unknown --agent fails before registering jobs',t=>{
  const {root,run,execute}=setup(t);
  const {calls}=mockOpenclaw(root);
  const result=execute('--scheduler','openclaw','--no-chat-delivery','--agent','agbiss');
  assert.notEqual(result.status,0);
  assert.match(result.stderr,/"agbiss" is not on this host \(agents: fina\)/);
  assert.equal(calls('add').length,0); assert.equal(calls('edit').length,0);
  assert.equal(fs.existsSync(path.join(run,'cron-install.json')),false);
});

test('OpenClaw agent: a reinstall without --agent keeps the recorded agent or fails',t=>{
  const {root,run,execute}=setup(t);
  mockOpenclaw(root,[{id:'fina',isDefault:true},{id:'agbis'}]);
  let result=execute('--scheduler','openclaw','--no-chat-delivery','--agent','agbis'); assert.equal(result.status,0,result.stderr);
  const {calls}=mockOpenclaw(root,[{id:'fina',isDefault:true},{id:'agbis'}]);
  result=execute('--scheduler','openclaw','--no-chat-delivery');
  assert.notEqual(result.status,0);
  assert.match(result.stderr,/installed for agent "agbis", but it now resolves to "fina"/);
  assert.match(result.stderr,/--agent agbis/);
  assert.equal(calls('add').length,0); assert.equal(calls('edit').length,0);
  assert.equal(JSON.parse(fs.readFileSync(path.join(run,'cron-install.json'))).agent.id,'agbis');
});

test('OpenClaw agent: no default agent fails before registering jobs',t=>{
  const {root,run,execute}=setup(t);
  for(const agents of [[{id:'fina'},{id:'agbis'}],[]]) {
    const {calls}=mockOpenclaw(root,agents);
    const result=execute('--scheduler','openclaw','--no-chat-delivery');
    assert.notEqual(result.status,0);
    assert.match(result.stderr,/No default OpenClaw agent/);
    assert.match(result.stderr,/--agent <id>/);
    assert.equal(calls('add').length,0); assert.equal(calls('edit').length,0);
    assert.equal(fs.existsSync(path.join(run,'cron-install.json')),false);
  }
  const {calls}=mockOpenclaw(root);
  const result=execute('--scheduler','openclaw','--no-chat-delivery','--agent');
  assert.notEqual(result.status,0); assert.match(result.stderr,/--agent needs an agent id/);
  assert.equal(calls('add').length,0);
});

test('OpenClaw agent: a failing agents list keeps its real error',t=>{
  const {root,run,execute}=setup(t);
  let {calls}=mockOpenclaw(root,'fail');
  let result=execute('--scheduler','openclaw','--no-chat-delivery');
  assert.notEqual(result.status,0);
  assert.match(result.stderr,/Cannot read OpenClaw agents.*gateway token mismatch/);
  assert.match(result.stderr,/pass --agent <id>/);
  assert.equal(calls('add').length,0);
  assert.equal(fs.existsSync(path.join(run,'cron-install.json')),false);
  // An explicit --agent still installs, with a warning.
  result=execute('--scheduler','openclaw','--no-chat-delivery','--agent','agbis');
  assert.equal(result.status,0,result.stderr);
  assert.match(result.stderr,/WARNING: --agent agbis not checked.*gateway token mismatch/);
  for(const argv of calls('add')) assert.equal(flagValue(argv,'--agent'),'agbis');
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(run,'cron-install.json'))).agent,{id:'agbis',source:'--agent (unverified)'});
});

test('OpenClaw agent: the deepest workspace is compared by real path',t=>{
  const {root,run,execute}=setup(t);
  // outer is written long but resolves to root; inner is a short link that
  // resolves to the run dir itself, so it is the deeper workspace.
  const link=path.join(root,'z'); fs.symlinkSync(run,link);
  const {calls}=mockOpenclaw(root,[
    {id:'outer',isDefault:true,workspace:root+'/.'.repeat(20)},
    {id:'inner',workspace:link},
  ]);
  const result=execute('--scheduler','openclaw','--no-chat-delivery'); assert.equal(result.status,0,result.stderr);
  for(const argv of calls('add')) assert.equal(flagValue(argv,'--agent'),'inner');
});

test('OpenClaw agent: one agent without a default flag, and the {agents:[...]} shape',t=>{
  const {root,run,execute}=setup(t);
  for(const [agents,id,source] of [
    [[{id:'solo'}],'solo','only openclaw agent'],
    [{agents:[{id:'wrapped',isDefault:true}]},'wrapped','openclaw default agent'],
  ]) {
    fs.rmSync(path.join(run,'cron-install.json'),{force:true});
    const {calls}=mockOpenclaw(root,agents);
    const result=execute('--scheduler','openclaw','--no-chat-delivery'); assert.equal(result.status,0,result.stderr);
    for(const argv of calls('add')) assert.equal(flagValue(argv,'--agent'),id);
    assert.deepEqual(JSON.parse(fs.readFileSync(path.join(run,'cron-install.json'))).agent,{id,source});
  }
});

test('OpenClaw agent: dry-run shows the agent the jobs would run as',t=>{
  const {root,execute}=setup(t);
  mockOpenclaw(root,[{id:'agbis',isDefault:true}]);
  let plan=JSON.parse(execute('--scheduler','openclaw','--dry-run').stdout);
  assert.deepEqual(plan.agent,{id:'agbis',source:'openclaw default agent'});
  mockOpenclaw(root,[]);
  const result=execute('--scheduler','openclaw','--dry-run'); assert.equal(result.status,0,result.stderr);
  assert.match(JSON.parse(result.stdout).agent.error,/No default OpenClaw agent/);
});

test('OpenClaw delivery target can come from run-spec notifications',t=>{
  const {root,run,execute}=setup(t);
  const {calls}=mockOpenclaw(root);
  fs.writeFileSync(path.join(run,'run-spec.json'),JSON.stringify({...DUBAI_SPEC,
    notifications:{deliver_channel:'slack',deliver_to:'channel:CSPEC'}}));
  const result=execute('--scheduler','openclaw'); assert.equal(result.status,0,result.stderr);
  for(const argv of calls('add')) assert.equal(flagValue(argv,'--to'),'channel:CSPEC');
  assert.equal(JSON.parse(fs.readFileSync(path.join(run,'cron-install.json'))).delivery.source,'run-spec notifications');
});

test('OpenClaw install without a delivery target fails before registering jobs',t=>{
  const {root,run,execute}=setup(t);
  const {calls}=mockOpenclaw(root);
  for(const extra of [[],['--deliver-to','channel:C1']]) {
    const result=execute('--scheduler','openclaw',...extra);
    assert.notEqual(result.status,0);
    assert.match(result.stderr,/explicit chat delivery target/);
    assert.match(result.stderr,/--no-chat-delivery/);
    assert.equal(calls('add').length,0); assert.equal(calls('edit').length,0);
    assert.equal(fs.existsSync(path.join(run,'cron-install.json')),false);
  }
});

test('--no-chat-delivery disables runner delivery and is recorded',t=>{
  const {root,run,execute}=setup(t);
  const {calls}=mockOpenclaw(root);
  const result=execute('--scheduler','openclaw','--no-chat-delivery'); assert.equal(result.status,0,result.stderr);
  for(const argv of calls('add')) {
    assert.ok(argv.includes('--no-deliver'));
    assert.ok(!argv.includes('--announce')); assert.ok(!argv.includes('--channel')); assert.ok(!argv.includes('--to'));
  }
  const receipt=JSON.parse(fs.readFileSync(path.join(run,'cron-install.json')));
  assert.equal(receipt.delivery.mode,'none'); assert.equal(receipt.delivery.source,'--no-chat-delivery');
  assert.deepEqual(receipt.delivery.openclaw_flags,['--no-deliver']);
});

test('no campaign schedule keeps the 24/7 UTC cadence',t=>{
  const {root,run,execute}=setup(t);
  const {jobArgs}=mockOpenclaw(root);
  const result=execute('--scheduler','openclaw','--no-chat-delivery'); assert.equal(result.status,0,result.stderr);
  assert.equal(flagValue(jobArgs('add','reply'),'--cron'),'5 * * * *');
  assert.equal(flagValue(jobArgs('add','reply'),'--tz'),'UTC');
  assert.equal(flagValue(jobArgs('add','monitor'),'--cron'),'15 * * * *');
  assert.equal(flagValue(jobArgs('add','monitor'),'--tz'),'UTC');
  const receipt=JSON.parse(fs.readFileSync(path.join(run,'cron-install.json')));
  assert.equal(receipt.send_window.applied,false); assert.match(receipt.send_window.reason,/no campaign.schedule/);
});

test('send window: numeric day keys, odd minutes and dry-run preview',t=>{
  const {root,run,execute}=setup(t);
  mockOpenclaw(root);
  fs.writeFileSync(path.join(run,'run-spec.json'),JSON.stringify({campaign:{schedule:{
    timing:{from:'08:30',to:'17:30'},timezone:'Europe/Berlin',
    days:{0:false,1:true,2:false,3:true,4:true,5:true,6:true}}}}));
  const result=execute('--scheduler','openclaw','--dry-run'); assert.equal(result.status,0,result.stderr);
  const plan=JSON.parse(result.stdout);
  assert.equal(plan.send_window.reply,'5 7-19 * * 1,3-6');
  assert.equal(plan.jobs.find(j=>j.key==='monitor').schedule,'15 7-19 * * 1,3-6');
  assert.equal(plan.jobs.find(j=>j.key==='monitor').tz,'Europe/Berlin');
  assert.equal(plan.delivery.mode,'missing');
});

test('unix cron keeps the 24/7 host-time cadence even with a campaign schedule',t=>{
  const {run,store,execute}=setup(t);
  fs.writeFileSync(path.join(run,'run-spec.json'),JSON.stringify(DUBAI_SPEC));
  const result=execute(); assert.equal(result.status,0,result.stderr);
  const table=fs.readFileSync(store,'utf8');
  assert.ok(table.includes('5 * * * * /bin/sh')); assert.ok(table.includes('15 * * * * /bin/sh'));
  const receipt=JSON.parse(fs.readFileSync(path.join(run,'cron-install.json')));
  assert.equal(receipt.send_window.applied,false); assert.equal(receipt.delivery,undefined);
});

test('send window: numeric day keys without "0"/"1" are still numeric (Tue-Fri)',t=>{
  const {root,run,execute}=setup(t);
  mockOpenclaw(root);
  fs.writeFileSync(path.join(run,'run-spec.json'),JSON.stringify({campaign:{schedule:{
    timing:{from:'09:00',to:'17:00'},timezone:'Asia/Dubai',days:{2:true,3:true,4:true,5:true}}}}));
  const result=execute('--scheduler','openclaw','--dry-run'); assert.equal(result.status,0,result.stderr);
  const plan=JSON.parse(result.stdout);
  assert.equal(plan.send_window.applied,true);
  assert.equal(plan.send_window.reply,'5 8-19 * * 2-5');
  assert.equal(plan.send_window.monitor,'15 8-19 * * 2-5');
  assert.deepEqual(plan.send_window.sending.days,[2,3,4,5]);
});
