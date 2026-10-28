import { createRequire } from 'node:module';
import test from 'node:test';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const model=require('../webos-home/model.js');

test('all canonical profile frames retain source geometry',()=>{
  assert.deepEqual(model.profile('aurora').cards,[80,298,1772,740]);
  assert.deepEqual(model.profile('hanoi2').cards,[1165,265,1960,1012]);
  assert.equal(model.profile('hanoi').sidebar,true);
  assert.equal(model.profile('hanoi3').tiles[0],1580);
});
test('widget switches remove cards, missing data produces no invented values',()=>{
  assert.deepEqual(model.cards({design_profile:'hanoi3',show_weather:false,show_gold:false,show_fuel:false,show_calendar:false},{}),[]);
  const cards=model.cards({design_profile:'aurora'},{});
  assert.equal(cards[0].key,'weather');
  assert.match(cards[0].lines.join(' '),/Chưa có dữ liệu/);
  assert.doesNotMatch(cards[0].lines.join(' '),/28°/);
});
test('zero values are displayed rather than treated as unavailable',()=>{
  const weather=model.cards({design_profile:'hanoi3'},{weather:{temp:0,humidity:0}})[0];
  assert.ok(weather.lines.includes('0°C'));
});
test('app order honors mapped dock, hidden apps and valid saved order',()=>{
 const apps=[{id:'a',title:'A'},{id:'b',title:'B'},{id:'c',title:'C'}];
 assert.deepEqual(model.orderedApps({dock_apps:['b'],hidden_apps:['c']},apps).map(a=>a.id),['b','a']);
 assert.deepEqual(model.orderedApps({},apps,['c','unknown','c']).map(a=>a.id),['c','a','b']);
 assert.equal(apps.length,3);
});
test('vertical focus and empty collections remain bounded',()=>{
 assert.equal(model.nextFocus(0,38,0,true),0);
 assert.equal(model.nextFocus(1,40,2,true),1);
 assert.equal(model.nextFocus(1,38,2,true),0);
});
test('calendar and gold consume canonical Python widget snapshot schema',()=>{
 const cards=model.cards({design_profile:'hanoi3'},{lunar:{solar:'2026-10-28',lunar_day:19,lunar_month:9,year_name:'Bính Ngọ',events:[{name:'Rằm',label:'15/11'}]},gold:{items:[{name:'SJC',buy:100,sell:110}]}});
 assert.match(cards.find(c=>c.key==='calendar').lines.join(' '),/19\/9/);
 assert.match(cards.find(c=>c.key==='gold').lines.join(' '),/SJC/);
});
test('theme input-pill and app-library switches control launcher actions',()=>{
 assert.deepEqual(model.actions({show_inputs_pill:false,app_library:false}),['settings']);
 assert.deepEqual(model.actions({}),['library','inputs','settings']);
});
