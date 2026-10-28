/** Run with jsdom@24 available: NODE_PATH=/path/to/node_modules node tests/lg_webos_ui_smoke.js */
const {JSDOM, ResourceLoader} = require('jsdom');
const assert = require('node:assert/strict');
const path = require('node:path');
class LocalOnly extends ResourceLoader { fetch(url, options) { return url.startsWith('file:') ? super.fetch(url, options) : Promise.resolve(Buffer.from('')); } }
const calls=[];
const lg={host:'192.168.1.9',port:3001,name:'LG',platform:'lg_webos',online:true};
const android={host:'192.168.1.8',port:5555,name:'Android',online:true};
const theme={id:'ha-noi-night-3',name:'Hà Nội 3',config:{dashboard:true,design_profile:'hanoi3'},errors:[],warnings:[],has_config:true};
const handlers={list_devices:async()=>[lg,android],app_version:async()=> '1.9.0',
 get_home_widgets_settings:async()=>({}),get_app_settings:async()=>({}),
 list_gathin_themes:async()=>[theme],current_launcher_theme:async()=>({config:theme.config,last_theme_id:theme.id}),
 list_apps:async()=>({apps:[{package:'netflix',name:'Netflix',enabled:true,type:'user'}]}),
 list_inputs:async()=>[{id:'HDMI_1',label:'Console'}],
 get_theme_widgets:async()=>[],apply_gathin_theme_job:async()=>({status:'done',steps:[],result:{}}),
 webos_apply_theme_async:async()=>({job_id:'lg1'})};
const delay=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const dom=await JSDOM.fromFile(path.resolve(__dirname,'../ui/index.html'),{runScripts:'dangerously',resources:new LocalOnly(),pretendToBeVisual:true,beforeParse(w){w.confirm=()=>true;w.alert=()=>{};w.matchMedia=()=>({matches:false,addEventListener(){}});w.pywebview={api:new Proxy({},{get:(_,key)=>(...args)=>{calls.push([key,...args]);return (handlers[key]||(async()=>null))(...args);}})};}});
 try {
 const w=dom.window; const $=id=>w.document.getElementById(id);const errors=[];w.addEventListener('error',e=>errors.push(e.message));
 await delay(500); await w.eval('refreshList()');
 w.document.querySelector('[data-host="192.168.1.9"][data-act="control"]').click();await delay(50);
 assert.equal(w.eval('activeDevice.platform'),'lg_webos');
 assert.equal($('tabApkBtn').hidden,true);assert.equal($('tabGuardBtn').disabled,true);assert.equal($('remoteScreencapBtn').hidden,true);
 const before=calls.length;await w.eval('loadApps()');
 assert.equal(w.document.querySelectorAll('#appsList [data-act="open"]').length,1);
 assert.equal(w.document.querySelectorAll('#appsList [data-act="disable"],#appsList [data-act="uninstall"],#appsList [data-act="stop"]').length,0);
 assert.equal($('appsList').textContent.includes('Netflix'),true);
 $('tabHomeBtn').click();await delay(100);
 assert.equal($('webosHomeSetup').hidden,false);
 await w.eval("applyTheme('ha-noi-night-3', null, {skipConfirm:true})");
 assert(calls.some(c=>c[0]==='webos_apply_theme_async'&&c[4]==='lgtv'));
 handlers.apply_gathin_theme_job=async()=>({status:'failed',error:'CLI unavailable',steps:[]});
 await w.eval("applyTheme('ha-noi-night-3', null, {skipConfirm:true})");
 assert($('homeStatus').textContent.includes('CLI unavailable'));
 assert($('homeActiveUpdated').textContent.includes('chưa xác minh'));
 const originalCurrent=handlers.current_launcher_theme;
 handlers.current_launcher_theme=async()=>{throw new Error('LG state unavailable');};
 await w.eval('loadCurrentTheme()');
 assert($('homeStatus').textContent.includes('LG state unavailable'));
 handlers.current_launcher_theme=originalCurrent;
 handlers.apply_gathin_theme_job=async()=>({status:'done',steps:[],result:{}});
 assert.equal(calls.slice(before).some(c=>['detect_launcher','launcher_wallpaper_preview','capture_theme_screenshot','get_apps_info','build_and_install_gathin_async','guard_status'].includes(c[0])),false);
 await w.eval('loadWebosInputs()');$('webosInputSwitch').click();await delay(20);
 assert(calls.some(c=>c[0]==='switch_input'&&c[3]==='HDMI_1'));
 const androidBtn=w.document.querySelector('[data-host="192.168.1.8"][data-act="control"]');androidBtn.click();await delay(20);
 assert.equal($('tabApkBtn').hidden,false);assert.equal($('tabGuardBtn').disabled,false);assert.equal($('webosHomeSetup').hidden,true);
 assert.deepEqual(errors,[]);
 console.log('PASS LG UI: saved selection, capability gates, app launch-only, same-catalog apply, HDMI, Android return');
 } finally {dom.window.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
