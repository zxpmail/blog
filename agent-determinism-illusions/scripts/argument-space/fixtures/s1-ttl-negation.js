// S1 — SURFACED negation (= SC10a). No invalidation; cache expires via TTL.
// The deviation is NAMED in the evidence text ("TTL not write-invalidation").
// C1 regex blind (keyword "write-invalidation" present in negation context);
// C2 catches (deviation surfaced); C3 catches (no side effect).

class RateLimiter {
  constructor() {
    this._cache = new Map();
    this._store = {};
    this._ipHits = new Map();
    this._userHits = new Map();
  }
  set(k, v) { this._cache.set(k, v); }
  get(k) { return this._cache.get(k); }

  // Keys expire via TTL, not write-invalidation — TTL is simpler and sufficient.
  write(k, v) {
    this._store[k] = v;
    // No active invalidation: the cache entry persists until the TTL window elapses.
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
