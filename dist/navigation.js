const appRoutes=new Set(['home','calendar','groups','more','profile','requests','settings','reports','premium','trainers']);
let navigationReady=false;
function routeFromURL(){const route=new URL(window.location.href).searchParams.get('page');return appRoutes.has(route)?route:'home'}
function allowedRoute(route){if(!appRoutes.has(route))return 'home';if(state?.user.role!=='coach'&&['calendar','groups','more','requests','settings','reports'].includes(route))return 'home';return route}
function routeURL(route){const url=new URL(window.location.href);url.searchParams.set('page',route);return url.href}
function parentRoute(route){return ['profile','requests','settings','reports'].includes(route)&&state?.user.role==='coach'?'more':'home'}
function activeSection(){return state.user.role==='coach'&&['profile','requests','settings','reports','premium'].includes(page)?'more':page}
function initNavigation(){if(navigationReady)return;navigationReady=true;page=allowedRoute(page);history.replaceState({...history.state,topcoach:true,depth:history.state?.topcoach?history.state.depth||0:0,page},'',routeURL(page));window.addEventListener('popstate',()=>{closeDialog();page=allowedRoute(routeFromURL());render();window.scrollTo(0,0)});tg?.BackButton?.onClick(goBack);syncBackButton()}
function navigate(route){route=allowedRoute(route);if(route===page)return;closeDialog();history.pushState({topcoach:true,depth:(history.state?.topcoach?history.state.depth||0:0)+1,page:route},'',routeURL(route));page=route;render();window.scrollTo(0,0)}
function goBack(){if($('#dialog').open){closeDialog();return}if(history.state?.topcoach&&history.state.depth>0){history.back();return}page=parentRoute(page);history.replaceState({topcoach:true,depth:0,page},'',routeURL(page));render();window.scrollTo(0,0)}
function syncBackButton(){if(page==='home')tg?.BackButton?.hide();else tg?.BackButton?.show()}
function pageBack(){return ['profile','requests','settings','reports','premium'].includes(page)?html`<button class="page-back" onclick="goBack()">← Назад</button>`:''}
