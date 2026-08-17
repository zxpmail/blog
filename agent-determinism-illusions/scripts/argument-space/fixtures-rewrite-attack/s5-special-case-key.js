// S5 — SPECIAL-CASE FIXTURE KEY (rewrite-attack vector #1, "Peter").
//
// The impl LOOKS compliant to C3 because it invalidates the cache entry
// when its key is written — but ONLY when the key happens to be the
// verify runner's hardcoded "key1". Any other key in production survives
// the write with the stale value still cached.
//
// C3 (verify-write-invalidation.js) probes only key1, so it PASSes here.
// The predicate C3 thinks it observed — "write(k) invalidates cache[k]" —
// holds for k = "key1" and silently fails for k = anything else.
//
// This is Peter's named vector: "special-casing the fixture key without
// implementing the intended invariant generally." The verify runner reads
// the referent the CLAIM names ("key"), but the producer can implement
// the side effect for one key while leaving the invariant unimplemented
// for the population the claim is actually about.

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
    // SPECIAL-CASE: only invalidate the fixture key the verify runner uses.
    // Real production writes (any key other than "key1") leak stale cache.
    if (k === "key1") {
      this._cache.delete(k);
    }
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
