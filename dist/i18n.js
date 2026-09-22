let uiLanguage='en',uiCatalog={};
const localeCache={},patternCache={};
async function loadLanguage(language='en'){
 const next=['ru','en','kaz'].includes(language)?language:'en';
 if(!localeCache[next]){const response=await fetch('locales/'+next+'.json',{cache:'no-store'});if(!response.ok)throw Error('Could not load language');localeCache[next]=await response.json()}
 uiLanguage=next;uiCatalog=localeCache[next];document.documentElement.lang=next==='kaz'?'kk':next;
}
function t(text){
 if(uiLanguage==='ru'||typeof text!=='string')return text;
 if(Object.prototype.hasOwnProperty.call(uiCatalog,text))return uiCatalog[text];
 // Translate only static source fragments. Template substitutions (names, comments,
 // court addresses and user input) never pass through this function.
 const keys=Object.keys(uiCatalog).filter(k=>!k.startsWith('bot.')).sort((a,b)=>b.length-a.length);
 if(!keys.length)return text;
 const escape=s=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
 const pattern=patternCache[uiLanguage]||(patternCache[uiLanguage]=new RegExp('(^|[^\\p{L}])('+keys.map(escape).join('|')+')(?=$|[^\\p{L}])','gu'));
 return text.replace(pattern,(match,prefix,key)=>prefix+uiCatalog[key]);
}
function html(strings,...values){return strings.map((part,i)=>t(part)+(i<values.length?values[i]:'')).join('')}
function locale(){return {ru:'ru-RU',en:'en-GB',kaz:'kk-KZ'}[uiLanguage]||'ru-RU'}
