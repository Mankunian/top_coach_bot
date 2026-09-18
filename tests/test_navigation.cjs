const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const vm=require('node:vm');
function app(url,role='coach'){
 const listeners={},dialog={open:false};const entries=[{url,state:null}];let index=0;
 const c={URL,state:{user:{role}},page:null,render:()=>{},closeDialog:()=>{dialog.open=false},$:()=>dialog,tg:{BackButton:{onClick:fn=>{c.back=fn},show:()=>{},hide:()=>{}}}};
 c.window={location:{href:url},addEventListener:(name,fn)=>listeners[name]=fn,scrollTo:()=>{}};
 c.history={get state(){return entries[index].state},replaceState(state,unused,url){entries[index]={state,url};c.window.location.href=url},pushState(state,unused,url){entries.splice(++index);entries.push({state,url});c.window.location.href=url},back(){if(index){index--;c.window.location.href=entries[index].url;listeners.popstate()}},forward(){if(index+1<entries.length){index++;c.window.location.href=entries[index].url;listeners.popstate()}}};
 vm.createContext(c);vm.runInContext(fs.readFileSync('dist/navigation.js','utf8'),c);c.page=c.routeFromURL();c.initNavigation();return {c,dialog};
}
test('legacy request deep link opens requests, back safely goes to More and Home',()=>{
 const {c}=app('https://example.com/mini.html?page=requests&source=bot#tgWebAppData=kept');
 assert.equal(c.page,'requests');assert.equal(c.activeSection(),'more');
 c.goBack();assert.equal(c.page,'more');assert.equal(new URL(c.window.location.href).searchParams.get('source'),'bot');assert.equal(new URL(c.window.location.href).hash,'#tgWebAppData=kept');
 c.goBack();assert.equal(c.page,'home');
});
test('browser and Telegram back/forward preserve routes, dialog back closes first',()=>{
 const {c,dialog}=app('https://example.com/');
 c.navigate('more');c.navigate('profile');c.navigate('settings');
 dialog.open=true;c.back();assert.equal(dialog.open,false);assert.equal(c.page,'settings');
 c.back();assert.equal(c.page,'profile');c.history.forward();assert.equal(c.page,'settings');
 c.navigate('calendar');assert.equal(c.routeFromURL(),'calendar');assert.equal(c.activeSection(),'calendar');
 c.navigate('calendar');c.goBack();assert.equal(c.page,'settings');
});
test('all prior routes remain addressable; unknown and coach-only player links fall back',()=>{
for(const page of ['profile','settings','reports','premium','groups','calendar','student'])assert.equal(app('https://example.com/?page='+page).c.page,page);
 assert.equal(app('https://example.com/?page=unknown').c.page,'home');
 assert.equal(app('https://example.com/?page=requests','player').c.page,'home');
 assert.equal(app('https://example.com/?page=profile','player').c.page,'profile');
});

test('student route preserves the selected student id and returns to Groups',()=>{
 const {c}=app('https://example.com/?page=calendar');
 c.state={user:{role:'coach'},students:[{telegramId:42}]};
 c.navigateStudent(42);
 assert.equal(c.page,'student');assert.equal(new URL(c.window.location.href).searchParams.get('studentId'),'42');
 c.goBack();assert.equal(c.page,'calendar');
});
