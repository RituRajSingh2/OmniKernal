# OmniKernal — Phase 7 Performance Research Report

_Generated: 2026-03-06T05:31:07.287855+00:00_

---

## 1. Message Processing Latency

| Users | Min (ms) | Max (ms) | Mean (ms) |
|-------|----------|----------|-----------|
| 1 | 21.925 | 21.925 | 21.925 |
| 10 | 10.334 | 11.31 | 10.64 |
| 50 | 9.494 | 19.356 | 11.464 |

## 2. Plugin Load Time

- Iterations: 5
- Min: 7.993 ms
- Max: 9.137 ms
- **Mean: 8.715 ms**

## 3. DB Tool Lookup vs In-Memory Baseline

| Approach | Mean (ms) |
|----------|-----------|
| DB Query | 1.61 |
| Dict Baseline | 0.0002 |

- **Overhead factor: 9999.8x** (DB vs dict)

## 4. Memory per Profile (psutil RSS)

- Baseline: 56.95 MB
- After 1 profile: 56.95 MB (delta: +0.0 MB)
- After 2 profiles: 56.96 MB (delta: +0.01 MB)
- Headless enforced at 2 profiles: True

## 5. Concurrent Message Throughput

| Concurrent | Total (ms) | Per-msg (ms) | Throughput (msg/s) |
|------------|------------|--------------|-------------------|
| 1 | 16.933 | 16.562 | 59.1 |
| 10 | 222.05 | 105.034 | 45.0 |
| 50 | 881.321 | 333.316 | 56.7 |

## 6. Fault Isolation

- **Result: ✅ PASS**
- Engine crashed on bad command: False
- Good messages processed after fault: 2/2

**Notes:**
  - Good message 1 processed OK before fault injection.
  - Bad command handled gracefully (no crash).
  - Good message 2 processed OK after fault injection.

---

## Summary

| Metric | Result | Status |
|--------|--------|--------|
| Latency @ 1 user | 21.925 ms mean | ✅ |
| Latency @ 50 users | 11.464 ms mean | ✅ |
| Plugin load | 8.715 ms mean | ✅ |
| DB overhead | 9999.8x vs dict | ✅ |
| Fault isolation | ✅ PASS | ✅ |