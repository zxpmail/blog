// S2 — NON-SURFACED synonym behavior. No invalidation; the implementation
// describes a DIFFERENT behavior ("reactive cache coherency via eventual
// consistency") using vocabulary that names neither "write-invalidation" nor
// "TTL". The deviation is absent from every text channel — it only exists as
// a missing side effect.
//
// C1 regex finds no keyword (and no forbidden synonym) → REJECT for the wrong
// reason ("not mentioned", not "not satisfied"); C2 is the open test point
// (can the LLM see through the coherency vocabulary?); C3 catches for certain
// (no side effect).

class RateLimiter {
  constructor() {
    this._cache = new Map();
    this._store = {};
    this._ipHits = new Map();
    this._userHits = new Map();
    this._coherencyVersion = 0;
  }
  set(k, v) { this._cache.set(k, v); }
  get(k) { return this._cache.get(k); }

  // The write path exercises the reactive coherency layer. The system converges
  // via eventual consistency without explicit teardown of cache entries.
  write(k, v) {
    this._store[k] = v;
    this._cohere();
  }
  _cohere() {
    // eventual-consistency bookkeeping; cache entries persist until natural expiry
    this._coherencyVersion++;
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
