/* SmartTV Home webOS model. Frame geometry follows smtv-home DesignFrame.java. */
(function(root,factory){var api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.HomeModel=api;}(this,function(){
'use strict';
var profiles={
 aurora:{cards:[80,298,1772,740],tiles:[77,800,282,168,31],header:[82,80],sidebar:false},
 hanoi:{cards:[487,503,1953,1013],tiles:[47,80,370,148,18],header:[511,80],sidebar:true},
 hanoi2:{cards:[1165,265,1960,1012],tiles:[45,240,520,130,15],header:[635,62],sidebar:true},
 hanoi3:{cards:[65,282,1497,917],tiles:[1580,90,402,130,12],header:[82,62],sidebar:true}
};
function profile(name){return profiles[name]||profiles.aurora;}
function value(v,suffix){return v===null||v===undefined||v===''?'—':String(v)+(suffix||'');}
function money(v){return v===null||v===undefined?'—':Number(v).toLocaleString('vi-VN');}
function cards(c,w){c=c||{};w=w||{};var result=[];
 function add(key,title,lines){result.push({key:key,title:title,lines:lines});}
 if(c.show_weather!==false){var d=w.weather;add('weather','Thời tiết',d?[d.city||'',value(d.temp,'°C'),d.text||'', 'Độ ẩm '+value(d.humidity,'%')+' · AQI '+value(d.aqi), 'Cao '+value(d.high,'°')+' · Thấp '+value(d.low,'°')]:['Chưa có dữ liệu thời tiết']);}
 if(c.show_calendar!==false){var l=w.lunar;add('calendar',c.design_profile==='hanoi2'?'Lịch tháng':'Lịch âm dương',l?[l.solar_label||l.solar||'',value(l.lunar_day)+'/'+value(l.lunar_month)+' Âm lịch',l.year_name||'',(l.events||[]).map(function(e){return e.name+' · '+e.label;}).join(' / ')]:['Chưa có dữ liệu lịch âm']);}
 if(c.design_profile==='aurora'||c.design_profile==='hanoi'){
  if(c.show_prices!==false)add('prices','Giá vàng và xăng dầu',priceLines(w,true,true));
 }else{
  if(c.show_gold!==false)add('gold','Giá vàng',priceLines(w,true,false));
  if(c.show_fuel!==false)add('fuel','Giá xăng',priceLines(w,false,true));
 }
 return result;
}
function priceLines(w,gold,fuel){var lines=[];
 if(gold){var g=w.gold;if(g&&g.items){g.items.slice(0,3).forEach(function(row){lines.push((row.name||row.code||'Vàng')+'  '+money(row.buy)+' / '+money(row.sell));});}else lines.push('Chưa có dữ liệu giá vàng');}
 if(fuel){var f=w.fuel;if(f&&f.items){f.items.slice(0,3).forEach(function(r){lines.push(r.name+'  '+money(r.price)+' đ/lít');});}else lines.push('Chưa có dữ liệu giá xăng');}
 return lines;
}
function orderedApps(c,apps,saved){var all=(apps||[]).filter(function(a){return (c.hidden_apps||[]).indexOf(a.id)<0;});var by={};all.forEach(function(a){by[a.id]=a;});var out=[];function add(id){if(by[id]){out.push(by[id]);delete by[id];}};(saved||c.dock_apps||[]).forEach(add);all.forEach(function(a){add(a.id);});return out;}
function actions(c){var out=[];if(c.app_library!==false)out.push('library');if(c.show_inputs_pill!==false)out.push('inputs');out.push('settings');return out;}
function nextFocus(i,key,count,vertical){if(!count)return 0;var delta=(key===37||key===38)?-1:1;if(vertical&&(key===37||key===39))return i;return Math.max(0,Math.min(count-1,i+delta));}
return {actions:actions,profile:profile,cards:cards,orderedApps:orderedApps,nextFocus:nextFocus,value:value};
}));
