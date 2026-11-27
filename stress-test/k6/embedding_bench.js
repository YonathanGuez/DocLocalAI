// Isolates the embedding model limit (nomic-embed-text via Ollama).
// Every /api/chat call does at least one embedding call (often 2-3 with
// query expansion), so this throughput directly caps RAG throughput.
import http from 'k6/http';
import { check } from 'k6';
import { Trend } from 'k6/metrics';

const BASE_URL = __ENV.OLLAMA_URL || 'http://ollama:11434';
const MODEL = __ENV.EMBED_MODEL || 'nomic-embed-text';

const embedDuration = new Trend('embedding_duration_ms', true);

const QUERIES = [
  'pod crashloopbackoff troubleshooting',
  'service not reachable networking',
  'oomkilled memory limits',
  'liveness readiness probe failing',
  'oc describe pod events',
];

export const options = {
  scenarios: {
    embedding_concurrency: {
      executor: 'ramping-vus',
      startVUs: 2,
      stages: JSON.parse(__ENV.STAGES || JSON.stringify([
        { duration: '15s', target: 2 },
        { duration: '20s', target: 5 },
        { duration: '20s', target: 10 },
        { duration: '15s', target: 0 },
      ])),
      gracefulRampDown: '10s',
    },
  },
};

export default function () {
  const input = QUERIES[Math.floor(Math.random() * QUERIES.length)];
  const res = http.post(
    `${BASE_URL}/v1/embeddings`,
    JSON.stringify({ model: MODEL, input }),
    { headers: { 'Content-Type': 'application/json' }, timeout: '30s' },
  );

  check(res, { 'status is 200': (r) => r.status === 200 });
  embedDuration.add(res.timings.duration);
}
