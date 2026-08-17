// S8 — PROTOTYPE POISON, TARGETED (rewrite-attack vector: "replace a dependency").
//
// The impl does NOT invalidate. Instead, at module-load time it patches
// Map.prototype.has so the verify runner's specific probe key ("key1")
// reports as absent after write() has been called once.
//
// The dependency being replaced is Map.prototype.has itself — a global
// the verify runner inherits from the runtime, not from any contract.
// The runner trusts the prototype; the producer rewrites the prototype.
//
// Prediction:
//   C3 (verify-write-invalidation.js, key1, single channel)  → PASS (fooled)
//   PROD (random keys, 4 channels)                            → REJECT (caught)
//
// PROD catches it because the poison is hardcoded to key1 and PROD uses
// random keys; the random keys bypass the patch and reveal the stale
// entry via .get / iteration / size-drop. This isolates the value of
// the multi-channel + randomized-key design: it defeats data-channel
// poison that targets the original probe.

let writeCalled = false;
const originalHas = Map.prototype.has;
Map.prototype.has = function (key) {
  if (writeCalled && key === "key1") return false;
  return originalHas.call(this, key);
};

class RateLimiter {
  constructor() {
    this._cache = new Map();
    this._store = {};
    this._ipHits = new Map();
    this._userHits = new Map();
  }
  set(k, v) { this._cache.set(k, v); }
  get(k) { return this._cache.get(k); }

  write(k, v) {
    this._store[k] = v;
    writeCalled = true;
    // no real invalidation — the prototype patch hides the entry from .has
  }

  isRateLimited(ip) {
    const n = (this._ipHits.get(ip) || 0) + 1;
    this._ipHits.set(ip, n);
    return n > 100;
  }
  isRateLimitedUser(user) {
    const n = (this._userHits.get(user) || 0) + 1;
    this._userHits.set(user, n);
    return n > 100;
  }
}

module.exports = { RateLimiter };
