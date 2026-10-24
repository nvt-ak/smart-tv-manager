import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const {
  pickSmartCleanModelId,
  resolveModelPick,
  resolveRefreshPreferred,
  isCommittedModel,
  applyPopulatePick,
} = require('../ui/js/smart_clean_model_logic.js');

const LIST = ['auto/best-chat', 'auto/best-chaos', 'gpt-4o-mini', 'custom/model-a'];

describe('resolveModelPick', () => {
  it('keeps user choice A when settings preferred B (userLocked)', () => {
    const pick = resolveModelPick({
      list: LIST,
      current: 'custom/model-a',
      preferred: 'auto/best-chaos',
      autoPick: false,
      userLocked: true,
    });
    assert.equal(pick, 'custom/model-a');
  });

  it('keeps current A over preferred B even without lock when both in list', () => {
    const pick = resolveModelPick({
      list: LIST,
      current: 'custom/model-a',
      preferred: 'auto/best-chaos',
      autoPick: false,
      userLocked: false,
    });
    assert.equal(pick, 'custom/model-a');
  });

  it('uses preferred when current empty (initial load)', () => {
    const pick = resolveModelPick({
      list: LIST,
      current: '',
      preferred: 'auto/best-chaos',
      autoPick: false,
      userLocked: false,
    });
    assert.equal(pick, 'auto/best-chaos');
  });

  it('does not auto-pick default when autoPick false and no valid current/preferred', () => {
    const pick = resolveModelPick({
      list: LIST,
      current: '',
      preferred: 'missing/model',
      autoPick: false,
      userLocked: false,
    });
    assert.equal(pick, '');
  });

  it('auto-picks auto/* when autoPick true and no current', () => {
    const pick = resolveModelPick({
      list: LIST,
      current: '',
      preferred: '',
      autoPick: true,
      userLocked: false,
    });
    assert.equal(pick, 'auto/best-chat');
  });

  it('userLocked prevents autoPick from reverting to default B', () => {
    const pick = resolveModelPick({
      list: LIST,
      current: 'custom/model-a',
      preferred: 'auto/best-chaos',
      autoPick: true,
      userLocked: true,
    });
    assert.equal(pick, 'custom/model-a');
  });
});

describe('resolveRefreshPreferred', () => {
  it('after late fetch, keeps current A instead of stale preferred B', () => {
    const want = resolveRefreshPreferred({
      current: 'custom/model-a',
      preferred: 'auto/best-chaos',
      settingsModel: 'auto/best-chaos',
      list: LIST,
    });
    assert.equal(want, 'custom/model-a');
  });
});

describe('pickSmartCleanModelId', () => {
  it('prefers auto/best-chat over gpt-4o-mini', () => {
    assert.equal(pickSmartCleanModelId(LIST, ''), 'auto/best-chat');
  });
});

describe('isCommittedModel', () => {
  it('requires model to exist in list', () => {
    assert.equal(isCommittedModel('custom/model-a', LIST), true);
    assert.equal(isCommittedModel('nope', LIST), false);
  });
});

describe('applyPopulatePick', () => {
  it('freezes user choice when locked even if preferred is auto/best-chaos', () => {
    const r = applyPopulatePick({
      userLocked: true,
      current: 'custom/model-a',
      preferred: 'auto/best-chaos',
      list: LIST,
      autoPick: true,
    });
    assert.equal(r.frozen, true);
    assert.equal(r.pick, 'custom/model-a');
    assert.equal(r.changed, false);
  });
});
