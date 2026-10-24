/**
 * Pure model-picker rules (Smart Clean). Tested via tests/smart_clean_model_logic.test.mjs
 */
(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  } else {
    root.SmartCleanModelLogic = api;
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function smartCleanModelLogicFactory() {
  function pickSmartCleanModelId(list, preferredId) {
    const ids = Array.isArray(list) ? list.filter(Boolean) : [];
    const preferred = (preferredId || '').trim();
    if (preferred && ids.includes(preferred)) return preferred;
    const autoBest = ids.find((id) => id === 'auto/best-chat' || String(id).startsWith('auto/'));
    if (autoBest) return autoBest;
    const notDefaultOpenAi = ids.find((id) => id !== 'gpt-4o-mini');
    return notDefaultOpenAi || ids[0] || '';
  }

  /**
   * Chọn model sau khi có danh sách. userLocked = user đã chọn tay — không ghi đè bằng preferred/settings.
   */
  function resolveModelPick({
    list,
    current,
    preferred,
    autoPick = false,
    userLocked = false,
  }) {
    const ids = Array.isArray(list) ? list.filter(Boolean) : [];
    const cur = (current || '').trim();
    const pref = (preferred || '').trim();

    if (userLocked && cur && ids.includes(cur)) return cur;
    if (cur && ids.includes(cur)) return cur;
    if (pref && ids.includes(pref)) return pref;
    if (autoPick && ids.length) return pickSmartCleanModelId(ids, pref);
    return '';
  }

  /** Sau fetch API: ưu tiên model đang trên form, không nhảy về default. */
  function resolveRefreshPreferred({ current, preferred, settingsModel, list }) {
    const ids = Array.isArray(list) ? list.filter(Boolean) : [];
    const cur = (current || '').trim();
    if (cur && ids.includes(cur)) return cur;
    const pref = (preferred || '').trim();
    if (pref && ids.includes(pref)) return pref;
    const sett = (settingsModel || '').trim();
    if (sett && ids.includes(sett)) return sett;
    return '';
  }

  function isCommittedModel(modelId, list) {
    const id = (modelId || '').trim();
    const ids = Array.isArray(list) ? list : [];
    return Boolean(id && ids.includes(id));
  }

  /** Sau khi user chọn tay: chỉ cập nhật cache list, không đổi selection. */
  function applyPopulatePick({
    userLocked,
    current,
    preferred,
    list,
    autoPick = false,
  }) {
    const ids = Array.isArray(list) ? list.filter(Boolean) : [];
    const cur = (current || '').trim();
    if (userLocked && cur && ids.includes(cur)) {
      return { pick: cur, changed: false, frozen: true };
    }
    const pick = resolveModelPick({
      list: ids,
      current: cur,
      preferred,
      autoPick,
      userLocked,
    });
    return { pick, changed: pick !== cur, frozen: false };
  }

  return {
    pickSmartCleanModelId,
    resolveModelPick,
    resolveRefreshPreferred,
    isCommittedModel,
    applyPopulatePick,
  };
});
