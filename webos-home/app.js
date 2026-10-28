/* Native webOS renderer for SmartTV Manager catalog/config and widget snapshots. */
(function(){'use strict';
var R=window.SMARTTV_HOME||{},C=R.config||{},W=R.widgets||{},M=window.HomeModel,p=M.profile(C.design_profile),bridges=[];
var $=function(id){return document.getElementById(id);},home=$('home'),focusIndex=0,buttons=[],modal=false;
home.className='profile-'+(C.design_profile||'aurora');
function fit(){home.style.transform='scale('+Math.min(innerWidth/2000,innerHeight/1125)+')';}fit();window.addEventListener('resize',fit);
function box(el,a){el.style.left=a[0]+'px';el.style.top=a[1]+'px';el.style.width=(a[2]-a[0])+'px';el.style.height=(a[3]-a[1])+'px';}
function status(text){$('status').textContent=text;}
function luna(uri,payload){try{var bridge=new PalmServiceBridge();bridges.push(bridge);bridge.onservicecallback=function(raw){var result;try{result=JSON.parse(raw);}catch(e){result={returnValue:false};}if(result.returnValue===false)status('TV không thực hiện được thao tác: '+(result.errorText||uri));var i=bridges.indexOf(bridge);if(i>=0)bridges.splice(i,1);};bridge.call(uri,JSON.stringify(payload));}catch(e){status('Chức năng này cần chạy trên TV LG webOS.');}}
function launch(id){luna('luna://com.webos.applicationManager/launch',{id:id});}
var wallpapers=(R.wallpapers||[]).slice(),wall=0;if(C.wallpaper_order==='random')wallpapers.sort(function(){return Math.random()-.5;});
function wallpaper(){if(wallpapers.length&&C.wallpaper!==false)$('wallpaper').style.backgroundImage='url("'+wallpapers[wall].replace(/["\\]/g,'')+'")';else $('wallpaper').style.background=C.background_color||'#050a12';}
var dim=Number(C.wallpaper_dim);if(isFinite(dim)&&dim>0)$('wallpaper').style.opacity=String(1-Math.min(1,dim>1?dim/100:dim));
wallpaper();if(wallpapers.length>1&&C.wallpaper_rotation_minutes!==0&&C.wallpaper_rotation_seconds!==0){var seconds=Math.max(10,Number(C.wallpaper_rotation_seconds)||Number(C.wallpaper_rotation_minutes||5)*60);setInterval(function(){wall=(wall+1)%wallpapers.length;wallpaper();},seconds*1000);}
var header=document.querySelector('header');header.style.left=p.header[0]+'px';header.style.top=p.header[1]+'px';
function clock(){var now=new Date();$('clock').textContent=now.toLocaleTimeString('vi-VN',{hour:'2-digit',minute:'2-digit'});$('date').textContent=now.toLocaleDateString('vi-VN',{weekday:'long',day:'numeric',month:'long',year:'numeric'});$('greeting').textContent=C.greeting_name||'SmartTV Home';}
clock();setInterval(clock,10000);
if(C.show_lunar_header===true&&C.lunar_date!==false&&W.lunar)$('lunar-header').textContent='Âm lịch '+W.lunar.lunar_day+'/'+W.lunar.lunar_month+' · '+(W.lunar.year_name||'');
if(C.show_quote!==false)$('quote').textContent=C.tagline||'';
if(C.show_footer!==false){var a=document.createElement('span'),b=document.createElement('span');a.textContent=C.corner_bottom||'';b.textContent=C.corner_right||'';$('footer').appendChild(a);$('footer').appendChild(b);}
var container=$('cards');box(container,p.cards);
function month(card){var solar=W.lunar&&W.lunar.solar;if(!solar)return;var parts=solar.split('-'),year=+parts[0],month=+parts[1]-1,today=+parts[2],offset=(new Date(year,month,1).getDay()+6)%7,total=new Date(year,month+1,0).getDate();var grid=document.createElement('div');grid.className='month';['T2','T3','T4','T5','T6','T7','CN'].forEach(function(day){var s=document.createElement('span');s.textContent=day;grid.appendChild(s);});for(var n=0;n<offset+total;n++){var cell=document.createElement('span');var day=n-offset+1;cell.textContent=day>0?day:'';if(day===today)cell.className='today';grid.appendChild(cell);}card.appendChild(grid);}
var cards=C.dashboard===false?[]:M.cards(C,W);if(!cards.some(function(card){return card.key==='weather';}))container.classList.add('no-weather');
cards.forEach(function(card){var el=document.createElement('article');el.className='card '+card.key;var h=document.createElement('h2');h.textContent=card.title;el.appendChild(h);card.lines.forEach(function(line){if(!line)return;var t=document.createElement('p');t.textContent=line;el.appendChild(t);});
 if(card.key==='weather'&&W.weather&&W.weather.forecast&&C.design_profile!=='hanoi2'){var row=document.createElement('div');row.className='forecast';W.weather.forecast.slice(0,5).forEach(function(f){var d=document.createElement('div');d.textContent=f.label+'\n'+M.value(f.high,'°')+' / '+M.value(f.low,'°');row.appendChild(d);});el.appendChild(row);}
 if(card.key==='calendar'&&C.design_profile==='hanoi2')month(el);
 container.appendChild(el);});
var apps=M.orderedApps(C,R.apps||[]),nav=$('apps'),t=p.tiles;
nav.style.left=t[0]+'px';nav.style.top=t[1]+'px';nav.style.height=(p.sidebar?1000-t[1]:t[3]+18)+'px';nav.style.gap=t[4]+'px';
function appButton(app,parent){var btn=document.createElement('button');btn.className='app';btn.type='button';btn.title=app.title||app.id;btn.style.width=t[2]+'px';btn.style.height=t[3]+'px';var badge=document.createElement('span');badge.className='badge';badge.textContent=(app.title||app.id).substring(0,1).toUpperCase();var label=document.createElement('span');label.className='app-name';label.textContent=app.title||app.id;btn.appendChild(badge);btn.appendChild(label);btn.onclick=function(){app.action?app.action():launch(app.id);};parent.appendChild(btn);return btn;}
function focus(n){if(!buttons.length)return;focusIndex=Math.max(0,Math.min(buttons.length-1,n));buttons.forEach(function(b,i){b.classList.toggle('focused',i===focusIndex);});buttons[focusIndex].focus();buttons[focusIndex].scrollIntoView({block:'nearest',inline:'nearest'});}
function library(items,title){modal=true;$('library').hidden=false;$('library').textContent='';var h=document.createElement('h1');h.textContent=title+' · Back để đóng';$('library').appendChild(h);buttons=items.map(function(app){return appButton(app,$('library'));});focus(0);}
function build(){modal=false;$('library').hidden=true;nav.textContent='';buttons=apps.map(function(app){return appButton(app,nav);});if(M.actions(C).indexOf('library')>=0)buttons.push(appButton({id:'library',title:'Tất cả ứng dụng',action:function(){library(apps,'Ứng dụng');}},nav));if(M.actions(C).indexOf('inputs')>=0)buttons.push(appButton({id:'inputs',title:'HDMI / Live TV',action:function(){var inputs=(R.inputs||[]).filter(function(i){return i.appId;}).map(function(i){return {id:i.appId,title:i.label};});inputs.push({id:'com.webos.app.livetv',title:'Live TV'});library(inputs,'Nguồn vào');}},nav));buttons.push(appButton({id:'com.palm.app.settings',title:'Cài đặt'},nav));focus(0);}
build();document.addEventListener('keydown',function(e){var key=e.keyCode;if(key===461||key===27){if(modal)build();e.preventDefault();}else if(key>=37&&key<=40){focus(M.nextFocus(focusIndex,key,buttons.length,p.sidebar&&!modal));e.preventDefault();}else if(key===13&&buttons[focusIndex]){buttons[focusIndex].click();e.preventDefault();}});
document.addEventListener('webOSRelaunch',clock);document.addEventListener('visibilitychange',function(){if(!document.hidden)clock();});
status('Dữ liệu snapshot: '+(W.generated||R.data_updated_at||'chưa cập nhật')+' · Cập nhật bằng Áp dụng lại theme trong Manager.');
}());
