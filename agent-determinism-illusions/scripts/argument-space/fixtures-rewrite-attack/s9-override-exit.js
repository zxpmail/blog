// S9 — CONTROL-CHANNEL OVERRIDE (rewrite-attack vector: "replace a dependency",
// applied to the reporting channel rather than the data channel).
//
// The impl does NOT invalidate, and it does NOT tamper with Map. Instead
// it overrides process.exit so that any non-zero exit code — the channel
// the oracles use to report REJECT — is silently flipped to 0.
//
// The dependency being replaced is process.exit, which both oracles call
// to signal their verdict. The oracles harden the data channel (PROD
// reads four channels, randomized keys) but they assume the exit-code
// channel is intact. S9 breaks that assumption.
//
// Prediction:
//   C3   → PASS (data channel says REJECT, exit(1) → exit(0) → oracle reports PASS)
//   PROD → PASS (same — multi-channel probes flag REJECT, exit(1) → exit(0))
//
// This is the strongest demonstration of Peter's point: an oracle that
// shares a process with the impl can have its REPORTING channel tampered
// with, not just its data channel. No amount of probe diversification
// closes this — the producer just moves the fakery up one level, from
// "lie about the cache" to "lie about the verdict."

const realExit = process.exit.bind(process);
process.exit = function (code) {
  if (code !== 0) {
    // turn REJECT into PASS by flipping the exit code
    return realExit(0);
  }
  return realExit(code);
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
    // no invalidation, no prototype patch — the exit-code flip is enough
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
