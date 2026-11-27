// Baseline: pure HTTP/uvicorn overhead, no DB/RAG/LLM work.
// Used to separate "web server limit" from "RAG+LLM pipeline limit".
import http from 'k6/http';
import { check } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://api:8000';

export const options = {
  scenarios: {
    baseline: {
      executor: 'ramping-vus',
      startVUs: 5,
      stages: JSON.parse(__ENV.STAGES || JSON.stringify([
        { duration: '15s', target: 5 },
        { duration: '20s', target: 20 },
        { duration: '20s', target: 40 },
        { duration: '10s', target: 0 },
      ])),
      gracefulRampDown: '10s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
  },
};

export default function () {
  const res = http.get(`${BASE_URL}/health`);
  check(res, { 'status is 200': (r) => r.status === 200 });
}
