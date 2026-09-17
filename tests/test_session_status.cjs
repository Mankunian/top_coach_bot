const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
// Execute production rendering functions without starting the Mini App or polling.
const source=fs.readFileSync('dist/live.js','utf8');
const context={Date, state:null, day:'2026-09-17', e:String, money:String, heading:()=>'',weekCalendar:()=>'',premiumBanner:()=>'',modal:html=>{context.dialog=html}};
vm.createContext(context);
for(const name of ['sessionStatus','status','home','openSession']){
 const line=source.split('\n').find(line=>line.startsWith(`function ${name}(`));
 vm.runInContext(line,context);
}
const session={id:'s',status:'scheduled',begins:100,ends:3700,members:[],absent:[],date:'2026-09-17',time:'19:00',name:'Alpha',place:'Court'};
test('start inclusive, end exclusive; cancelled remains cancelled',()=>{
 for(const [now,expected] of [[99,'scheduled'],[100,'live'],[3699.999,'live'],[3700,'completed'],[3701,'completed']])assert.equal(context.sessionStatus(session,now),expected);
 assert.equal(context.sessionStatus({...session,status:'cancelled'},4000),'cancelled');
 assert.equal(context.sessionStatus({...session,status:'completed'},50),'completed');
});
test('stale scheduled response renders ended card and disables attendance after reopening',()=>{
 context.state={user:{role:'coach'},sessions:[session],students:[]};
 assert.equal(context.status(session),'Завершена');
 const html=context.home();assert.match(html,/session completed/);assert.doesNotMatch(html,/session live|Тренировка идёт/);
 context.openSession('s');assert.doesNotMatch(context.dialog,/Отменить тренировку/);
 context.state.sessions=[{...session,members:[20]}];context.openSession('s');assert.match(context.dialog,/disabled/);
});
