import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Trend } from "k6/metrics";

const baseUrl = (__ENV.API_URL || "http://127.0.0.1:8000/api/v1/orders").replace(/\/$/, "");
const token = __ENV.API_TOKEN;
const restaurantId = __ENV.RESTAURANT_ID;
const productIds = (__ENV.PRODUCT_IDS || "")
  .split(",")
  .map((productId) => productId.trim())
  .filter(Boolean);
const runId = __ENV.RUN_ID;
const startedAt = Date.now();
const windowSeconds = 10;
const testDurationSeconds = 180;
const iterationPeriodMs = Number(__ENV.ITERATION_PERIOD_MS || "5000");
const vuCount = 50;
const requestWindows = Array.from(
  { length: 18 },
  (_, index) => new Counter(`requests_window_${String(index).padStart(2, "0")}`),
);
const readOrdersDuration = new Trend("read_orders_duration");
const createOrderDuration = new Trend("create_order_duration");
const cancelOrderDuration = new Trend("cancel_order_duration");

if (!token || !restaurantId || productIds.length < 50 || !runId) {
  throw new Error("Set API_TOKEN, RESTAURANT_ID, 50 PRODUCT_IDS, and a unique RUN_ID for this benchmark.");
}
if (!Number.isFinite(iterationPeriodMs) || iterationPeriodMs <= 0) {
  throw new Error("ITERATION_PERIOD_MS must be a positive number.");
}
if (new Set(productIds).size !== productIds.length) {
  throw new Error("PRODUCT_IDS must contain unique product IDs.");
}

export const options = {
  vus: 50,
  duration: "3m",
  summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)"],
  thresholds: {
    http_req_duration: ["p(95)<200", "p(99)<500"],
    read_orders_duration: ["p(95)<200", "p(99)<500"],
    create_order_duration: ["p(95)<200", "p(99)<500"],
    cancel_order_duration: ["p(95)<200", "p(99)<500"],
    http_req_failed: ["rate<0.01"],
    checks: ["rate>0.99"],
  },
};

export default function () {
  if (__ITER === 0) {
    // Spread the first transaction of each VU across one cycle, then keep a
    // fixed cycle period to avoid synchronized write bursts.
    sleep(((__VU - 1) * iterationPeriodMs) / vuCount / 1000);
  }
  const iterationStartedAt = Date.now();
  const productId = productIds[(__VU - 1) % productIds.length];
  const authHeaders = { Authorization: `Bearer ${token}` };
  const headers = {
    ...authHeaders,
    "Content-Type": "application/json",
    "Idempotency-Key": `k6-${runId}-${__VU}-${__ITER}`,
  };
  const readStartedAt = Date.now();
  const ordersPage = http.get(`${baseUrl}?limit=20`, { headers: authHeaders });
  readOrdersDuration.add(ordersPage.timings.duration);
  recordRequest(readStartedAt);
  check(ordersPage, {
    "orders list returns 200": (res) => res.status === 200,
  });

  const body = JSON.stringify({
    restaurant_id: restaurantId,
    items: [{ product_id: productId, quantity: 1 }],
  });
  const createStartedAt = Date.now();
  const created = http.post(baseUrl, body, { headers });
  createOrderDuration.add(created.timings.duration);
  recordRequest(createStartedAt);
  const createdSuccessfully = check(created, {
    "order create returns 201": (res) => res.status === 201,
  });

  if (createdSuccessfully) {
    const orderId = created.json("id");
    const cancelStartedAt = Date.now();
    const cancelled = http.post(`${baseUrl}/${orderId}/cancel`, null, {
      headers: { Authorization: `Bearer ${token}` },
    });
    cancelOrderDuration.add(cancelled.timings.duration);
    recordRequest(cancelStartedAt);
    check(cancelled, {
      "order cancel returns 200": (res) => res.status === 200,
      "order is cancelled": (res) => res.json("status") === "CANCELLED",
    });
  }

  const remainingCycleMs = iterationPeriodMs - (Date.now() - iterationStartedAt);
  if (remainingCycleMs > 0) {
    sleep(remainingCycleMs / 1000);
  }
}

function recordRequest(requestStartedAt) {
  const elapsedSeconds = (requestStartedAt - startedAt) / 1000;
  if (elapsedSeconds < 0 || elapsedSeconds >= testDurationSeconds) {
    return;
  }
  const windowIndex = Math.floor(elapsedSeconds / windowSeconds);
  requestWindows[windowIndex].add(1);
}

export function handleSummary(data) {
  const latency = data.metrics.http_req_duration.values;
  const requestsPerSecond = data.metrics.http_reqs.values.rate;
  const errorRate = data.metrics.http_req_failed.values.rate * 100;
  const p95 = latency["p(95)"];
  const p99 = latency["p(99)"];
  const readLatency = data.metrics.read_orders_duration?.values ?? {};
  const createLatency = data.metrics.create_order_duration?.values ?? {};
  const cancelLatency = data.metrics.cancel_order_duration?.values ?? {};
  const readP95 = readLatency["p(95)"] ?? Number.POSITIVE_INFINITY;
  const readP99 = readLatency["p(99)"] ?? Number.POSITIVE_INFINITY;
  const createP95 = createLatency["p(95)"] ?? Number.POSITIVE_INFINITY;
  const createP99 = createLatency["p(99)"] ?? Number.POSITIVE_INFINITY;
  const cancelP95 = cancelLatency["p(95)"] ?? Number.POSITIVE_INFINITY;
  const cancelP99 = cancelLatency["p(99)"] ?? Number.POSITIVE_INFINITY;
  const durationSeconds = data.state.testRunDurationMs / 1000;
  const loadProfilePassed =
    data.metrics.vus_max.values.max === 50 && durationSeconds >= 180;
  const checkPasses = (name) =>
    data.root_group.checks.find((result) => result.name === name)?.passes ?? 0;
  const readRequests = checkPasses("orders list returns 200");
  const createdOrders = checkPasses("order create returns 201");
  const cancelledOrders = checkPasses("order cancel returns 200");
  const checksRate = data.metrics.checks?.values?.rate ?? 0;
  const finiteP99Values = [p99, readP99, createP99, cancelP99].filter(Number.isFinite);
  const latencyMax = Math.ceil(
    Math.max(500, ...finiteP99Values) * 1.1 / 50,
  ) * 50;
  const errorMax = Math.ceil(Math.max(1, errorRate) * 1.1 * 10) / 10;
  const windowRates = requestWindows.map((_, index) => {
    const metric = data.metrics[`requests_window_${String(index).padStart(2, "0")}`];
    return (metric ? metric.values.count : 0) / windowSeconds;
  });
  const steadyWindowRates = windowRates.slice(1, -1);
  const lowestWindowRps = Math.min(...steadyWindowRates);
  const highestWindowRps = Math.max(...steadyWindowRates);
  const meanWindowRps = steadyWindowRates.reduce((total, rate) => total + rate, 0) /
    steadyWindowRates.length;
  const rpsSpreadPercent = meanWindowRps
    ? ((highestWindowRps - lowestWindowRps) / meanWindowRps) * 100
    : Number.POSITIVE_INFINITY;
  const stableThroughput = steadyWindowRates.length === 16 &&
    meanWindowRps > 0 && rpsSpreadPercent < 20;
  const freshOrderFlowPassed = readRequests > 0 && createdOrders > 0 &&
    createdOrders === cancelledOrders;
  const passed = loadProfilePassed && stableThroughput && freshOrderFlowPassed &&
    p95 < 200 && p99 < 500 &&
    readP95 < 200 && readP99 < 500 &&
    createP95 < 200 && createP99 < 500 &&
    cancelP95 < 200 && cancelP99 < 500 &&
    errorRate < 1 && checksRate > 0.99;
  const rpsMax = Math.max(1, ...windowRates);
  const rpsAxisMax = Math.ceil(rpsMax / 10) * 10;
  const windowLabels = requestWindows.map((_, index) => `"${index * windowSeconds}"`).join(", ");
  const rpsValues = windowRates.map((rate) => rate.toFixed(2)).join(", ");
  const report = `# CP3 k6 Performance Results

| Metric | Result | Target | Status |
| --- | ---: | ---: | --- |
| Load profile | 50 VUs for 180 seconds (${durationSeconds.toFixed(0)} seconds total incl. graceful stop) | 50 VUs for 180 seconds | ${loadProfilePassed ? "Pass" : "Fail"} |
| Requests | ${data.metrics.http_reqs.values.count} total | — | Recorded |
| Read transactions | ${readRequests} successful order-list reads | At least one read per write iteration | ${readRequests > 0 ? "Pass" : "Fail"} |
| Fresh orders | ${createdOrders} created / ${cancelledOrders} cancelled | Each create gets one cancel | ${createdOrders > 0 && createdOrders === cancelledOrders ? "Pass" : "Fail"} |
| Throughput | ${requestsPerSecond.toFixed(2)} requests/s | — | Recorded |
| Steady 10-second RPS range | ${lowestWindowRps.toFixed(2)}-${highestWindowRps.toFixed(2)} requests/s (${rpsSpreadPercent.toFixed(1)}% of mean) | Spread < 20% across middle 160 seconds | ${stableThroughput ? "Pass" : "Fail"} |
| p95 latency | ${p95.toFixed(2)} ms | < 200 ms | ${p95 < 200 ? "Pass" : "Fail"} |
| p99 latency | ${p99.toFixed(2)} ms | < 500 ms | ${p99 < 500 ? "Pass" : "Fail"} |
| Order-list read p95 / p99 | ${readP95.toFixed(2)} / ${readP99.toFixed(2)} ms | < 200 / < 500 ms | ${readP95 < 200 && readP99 < 500 ? "Pass" : "Fail"} |
| Create order p95 / p99 | ${createP95.toFixed(2)} / ${createP99.toFixed(2)} ms | < 200 / < 500 ms | ${createP95 < 200 && createP99 < 500 ? "Pass" : "Fail"} |
| Cancel order p95 / p99 | ${cancelP95.toFixed(2)} / ${cancelP99.toFixed(2)} ms | < 200 / < 500 ms | ${cancelP95 < 200 && cancelP99 < 500 ? "Pass" : "Fail"} |
| HTTP error rate | ${errorRate.toFixed(3)}% | < 1% | ${errorRate < 1 ? "Pass" : "Fail"} |
| Check pass rate | ${(checksRate * 100).toFixed(2)}% | > 99% | ${checksRate > 0.99 ? "Pass" : "Fail"} |
| Overall CP3 load result | ${passed ? "Pass" : "Fail"} | Load profile, read/write mix, stable RPS, latency, and errors | ${passed ? "Pass" : "Fail"} |

Each iteration reads the latest page of up to 20 orders, creates a new order with a unique idempotency key, and cancels it once. The 50 VUs each use a different product/inventory row to avoid serializing all writes on one stock row. Their first transactions are staggered across a ${ (iterationPeriodMs / 1000).toFixed(1) }-second cycle, and each VU starts at most one transaction per cycle to avoid synchronized bursts. Supply 50 distinct active product IDs for the same restaurant, each with stock available throughout the run. Throughput stability excludes the first and last 10-second bins and requires the min-to-max spread to remain below 20% of the mean across the middle 160 seconds.

Test deployment: API and databases in Docker Compose, with k6 running in the Grafana k6 container on Windows.

## Latency chart

\`\`\`mermaid
xychart-beta
    x-axis ["p95 actual", "p95 target", "p99 actual", "p99 target"]
    y-axis "Latency (ms)" 0 --> ${latencyMax}
    bar [${p95.toFixed(2)}, 200, ${p99.toFixed(2)}, 500]
\`\`\`

## Error-rate chart

\`\`\`mermaid
xychart-beta
    x-axis ["Actual", "Target"]
    y-axis "HTTP errors (%)" 0 --> ${errorMax}
    bar [${errorRate.toFixed(3)}, 1]
\`\`\`

## Request throughput over time

\`\`\`mermaid
xychart-beta
    x-axis "Time (seconds)" [${windowLabels}]
    y-axis "Requests/s" 0 --> ${rpsAxisMax}
    line [${rpsValues}]
\`\`\`
`;

  return {
    "cp3-k6-summary.json": JSON.stringify(data, null, 2),
    "cp3-k6-report.md": report,
  };
}
