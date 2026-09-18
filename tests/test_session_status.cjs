const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
// Execute production rendering functions without starting the Mini App or polling.
const source=fs.readFileSync('dist/live.js','utf8');
const context={window:{t:s=>s},html:(strings,...values)=>strings.map((s,i)=>s+(i<values.length?values[i]:'')).join(''),locale:()=> 'ru-RU',Date, state:null, day:'2026-09-17', e:String, money:String, heading:()=>'',weekCalendar:()=>'',premiumBanner:()=>'',formatDate:value=>String(value).split('-').reverse().join('.'),modal:html=>{context.dialog=html}};
vm.createContext(context);
for(const name of ['sessionStatus','status','home','openSession','balanceLabel']){
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
for(const name of ['durationField','memberFields','addMember','assignMenu','paymentGroupLabel'])vm.runInContext(source.split('\n').find(line=>line.startsWith(`function ${name}(`)),context);
test('group form includes existing students from other groups, excludes only this group',()=>{
 context.state={students:[{telegramId:20,fullName:'Player'}],groups:[{id:'a',name:'A',members:[20],type:'Групповая'},{id:'b',name:'B',members:[],type:'Групповая'}]};
 assert.match(context.memberFields(),/value="20"/);
 assert.match(context.memberFields(context.state.groups[1]),/value="20"/);
 assert.doesNotMatch(context.memberFields(context.state.groups[0]),/value="20"/);
 context.addMember('b');assert.match(context.dialog,/player:20/);
 context.assignMenu(20);assert.match(context.dialog,/id:'b'/);assert.doesNotMatch(context.dialog,/id:'a'/);
 assert.match(context.durationField(90),/value="90" required/);
});
test('minute balances remain readable',()=>{
 assert.equal(context.balanceLabel(55/60),'55 мин');
 assert.equal(context.balanceLabel(115/60),'1 ч 55 мин');
 assert.equal(context.balanceLabel(0),'0 ч');
 assert.match(context.durationField(5),/value="60"/);assert.match(context.durationField(90),/min="60"/);
});
