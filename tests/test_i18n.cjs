const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const vm=require('node:vm');
const catalogs=Object.fromEntries(['ru','en','kaz'].map(l=>[l,JSON.parse(fs.readFileSync(`dist/locales/${l}.json`))]));
const context={document:{documentElement:{}},fetch:async path=>({ok:true,json:async()=>catalogs[path.split('/')[1].split('.')[0]]})};context.window=context;
vm.createContext(context);vm.runInContext(fs.readFileSync('dist/i18n.js','utf8'),context);
test('catalogs have matching keys and placeholders',()=>{
 for(const lang of ['en','kaz']){
  assert.deepEqual(Object.keys(catalogs[lang]).sort(),Object.keys(catalogs.ru).sort());
  for(const [key,text] of Object.entries(catalogs.ru))assert.deepEqual(catalogs[lang][key].match(/\{\w+\}/g)?.sort(),text.match(/\{\w+\}/g)?.sort(),key);
 }
});
test('language loads; static UI changes, user content is untouched',async()=>{
 await context.loadLanguage('en');assert.equal(context.t('Настройки'),'Settings');
 assert.equal(vm.runInContext('html`<h2>Группы</h2><p>${"Название"}</p>`',context),'<h2>Groups</h2><p>Название</p>');
 assert.equal(vm.runInContext('html`<label>Тип<select><option value="${"Групповая"}">Групповая</option></select></label>`',context),'<label>Type<select><option value="Групповая">Group training</option></select></label>');
 await context.loadLanguage('kaz');assert.equal(context.t('Сохранить'),'Сақтау');assert.equal(context.document.documentElement.lang,'kk');
 await context.loadLanguage('ru');assert.equal(context.t('Сохранить'),'Сохранить');
});
test('coach pages render with the actual locale engine',async()=>{
 const source=fs.readFileSync('dist/live.js','utf8');
 Object.assign(context,{e:s=>String(s??''),setTimeout:()=>{},$ :()=>({}),day:'2026-09-17',reportFrom:'2026-09-01',reportTo:'2026-09-17',tab:'groups',requestTab:'pending',money:n=>String(n),state:{user:{role:'coach',language:'en',fullName:'Test',city:'Astana',bio:'',reminderHours:1},groups:[],students:[],sessions:[],payments:[],requests:[],trainers:[]}});
 for(const line of source.split('\n').filter(line=>/^(async )?function /.test(line)))vm.runInContext(line,context);
 for(const [lang,label] of [['en','Settings'],['kaz','Баптаулар']]){
  await context.loadLanguage(lang);
  assert.match(context.settingsView(),new RegExp(label));
  for(const name of ['home','coachHome','moreView','requestsView','groupsView','profileView','reportsView','premiumView'])assert.equal(typeof context[name](),'string');
  assert.match(context.durationField(90),/min="60"/);
 }
 await context.loadLanguage('en');
 assert.match(context.profileView(),/Profile/);
 assert.match(context.groupsView(),/Groups and students/);
});
