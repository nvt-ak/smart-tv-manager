/* Platform policy shared by Manager UI event handlers. Legacy devices remain Android. */
(function () {
  'use strict';
  function normalize(device, saved) {
    var source = (saved || []).find(function (d) {
      return d.host === device.host && (!device.port || Number(d.port) === Number(device.port));
    }) || {};
    var result = Object.assign({}, source, device);
    result.platform = result.platform || 'android_tv';
    result.port = Number(result.port || (result.platform === 'lg_webos' ? 3001 : 5555));
    return result;
  }
  function policy(device) {
    var lg = !!device && device.platform === 'lg_webos';
    return {remote:true, apps:true, theme:true, inputs:lg, apk:!lg, guard:!lg,
      clean:!lg, shell:!lg, screenshot:!lg, defaultHome:!lg};
  }
  function appId(device, id) {
    if (!device || device.platform !== 'lg_webos') return id;
    return {'com.netflix.ninja':'netflix', 'com.google.android.youtube.tv':'youtube.leanback.v4',
      'com.amazon.amazonvideo.livingroom':'amazon', 'com.disney.disneyplus':'com.disney.disneyplus-prod'}[id] || null;
  }
  window.DevicePlatform = {normalize:normalize, policy:policy, appId:appId};
})();
