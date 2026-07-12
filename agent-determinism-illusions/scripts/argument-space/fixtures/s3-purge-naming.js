// S3 — SYNONYM NAMING (= SC13). Invalidation genuinely implemented, but the
// method is called purgeCacheOnWrite, not "invalidate". The behavior is correct;
// only the vocabulary differs.
//
// C1 regex (write.?invalidat) finds no keyword → FALSE REJECT (naming-sensitive);
// C2 passes (understands purge == invalidate from evidence); C3 passes (side
// effect present — method name irrelevant).

class RateLimiter {
  constructor() {
    this._cache = new Map();
    this._store = {};
    this._ipHits = new Map();
    this._userHits = new Map();
  }
  set(k, v) { this._cache.set(k, v); }
  get(k) { return this._cache.get(k); }

  // Cache is purged on write.
  write(k, v) {
    this._store[k] = v;
    this.purgeCacheOnWrite(k);   // ← real invalidation, just named differently
  }
  purgeCacheOnWrite(k) {
    this._cache.delete(k);        // actually invalidates — same side effect as S0
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
