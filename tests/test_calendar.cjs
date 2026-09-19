const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const vm=require('node:vm');
const dialogs=[];const context={Date,Math,Intl,window:{t:s=>s},state:{groups:[{id:'g',type:'Групповая'}],students:[{telegramId:20,fullName:'Алина',hours:1.5}],sessions:[{id:'a',group:'g',date:'2026-09-17',time:'18:00',name:'Альфа',place:'Корт 2',members:[20],begins:1789650000,ends:1789655400,durationMinutes:90,status:'scheduled'}]},render:()=>{context.rendered=true},modal:html=>dialogs.push(html),sessionStatus:s=>s.status,balanceLabel:hours=>`${hours} ч`,status:s=>s.status==='scheduled'?'Запланирована':s.status,localStorage:{},locale:()=> 'ru-RU',formatDate:value=>String(value).split('-').reverse().join('.'),e:s=>String(s)};
context.html=(strings,...values)=>strings.map((part,index)=>part+(index<values.length?values[index]:'' )).join('');
vm.createContext(context);vm.runInContext(fs.readFileSync('dist/calendar.js','utf8'),context);
test('month calendar displays session marker and opens day details',()=>{
 const markup=vm.runInContext("calendarMode='month';calendarCursor=new Date(2026,8,1);calendarView()",context);
 assert.match(markup,/calendar-count">1/);assert.match(markup,/openCalendarDay\('2026-09-17'\)/);
 vm.runInContext("openCalendarDay('2026-09-17')",context);
 assert.match(dialogs.pop(),/Корт 2/);
});
test('week calendar covers seven dates and keeps session detail participant link',()=>{
 const cells=vm.runInContext("calendarMode='week';calendarCursor=new Date(2026,8,17);calendarCells()",context);
 assert.equal((cells.match(/calendar-day/g)||[]).length,7);
 const details=context.sessionDetailCard(context.state.sessions[0]);
 assert.match(details,/navigateStudent\(20\)/);assert.match(details,/90 min/);
});
