import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs';
import vm from 'node:vm';
const context = { window: {} };
vm.runInNewContext(fs.readFileSync(new URL('../ui/js/device_platform.js', import.meta.url), 'utf8'), context);
const p = context.window.DevicePlatform;
test('saved LG platform survives selecting host/port-only button', () => {
 const device = p.normalize({host:'tv',port:3001}, [{host:'tv',port:3001,platform:'lg_webos',name:'LG'}]);
 assert.equal(device.platform,'lg_webos'); assert.equal(device.name,'LG');
});
test('legacy Android remains enabled while LG gates Android operations', () => {
 assert.equal(p.policy({host:'old'}).apk,true);
 const lg = p.policy({platform:'lg_webos'});
 for(const key of ['apk','guard','clean','shell','screenshot','defaultHome']) assert.equal(lg[key],false,key);
 for(const key of ['remote','apps','theme','inputs']) assert.equal(lg[key],true,key);
});
test('port alone never guesses platform; unknown quick apps are blocked on LG', () => {
 assert.equal(p.normalize({host:'tv',port:3001},[]).platform,'android_tv');
 assert.equal(p.appId({platform:'lg_webos'},'com.netflix.ninja'),'netflix');
 assert.equal(p.appId({platform:'lg_webos'},'com.unknown.app'),null);
 assert.equal(p.appId({},'com.netflix.ninja'),'com.netflix.ninja');
});
test('different TV cannot donate platform or credentials', () => {
 const row=p.normalize({host:'new'},[{host:'old',platform:'lg_webos'}]);
 assert.equal(row.platform,'android_tv'); assert.equal(row.port,5555);
});
