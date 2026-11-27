// End-to-end RAG+LLM load test against POST /api/chat.
// Simulates N concurrent users each holding their own chat session,
// ramping up in stages to find where latency/error rate break down.
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://api:8000';

const chatErrors = new Rate('chat_errors');
const chatDuration = new Trend('chat_duration_ms', true);
const timeouts = new Counter('chat_timeouts');
const rateLimited = new Counter('chat_rate_limited_429');
const serverErrors = new Counter('chat_server_errors_5xx');

// Drawn from the sample runbooks (pod troubleshooting / networking) plus a
// generic one, so retrieval has real content to match against.
const QUESTIONS = [
  'Why is my pod in CrashLoopBackOff?',
  'How do I check pod resource usage?',
  'My service is not reachable from within the cluster, what should I check?',
  'How do I fix an OOMKilled pod?',
  'What are the common causes of pod startup failures?',
  'How do I debug failing liveness probes?',
  'Service endpoints are empty, how do I troubleshoot?',
  'How do I check pod events in OpenShift?',
  'What causes connection timeouts between services?',
  'List the runbooks you have access to',
];

// Deterministic valid UUID per virtual user so each VU behaves like one
// returning user with a persistent session (realistic conversation history).
function uuidForVU(vu) {
  const hex = vu.toString(16).padStart(12, '0');
  return `00000000-0000-4000-8000-${hex}`;
}

export const options = {
  scenarios: {
    ramping_users: {
      executor: 'ramping-vus',
      startVUs: 2,
      stages: JSON.parse(__ENV.STAGES || JSON.stringify([
        { duration: '30s', target: 2 },
        { duration: '45s', target: 5 },
        { duration: '45s', target: 10 },
        { duration: '45s', target: 15 },
        { duration: '20s', target: 0 },
      ])),
      gracefulRampDown: '30s',
    },
  },
  thresholds: {
    chat_errors: ['rate<0.05'],
  },
};

export default function () {
  const sessionId = uuidForVU(__VU);
  const message = QUESTIONS[Math.floor(Math.random() * QUESTIONS.length)];

  const res = http.post(
    `${BASE_URL}/api/chat`,
    JSON.stringify({ session_id: sessionId, message }),
    { headers: { 'Content-Type': 'application/json' }, timeout: '120s' },
  );

  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
    'has reply body': (r) => {
      try {
        return !!JSON.parse(r.body).reply;
      } catch {
        return false;
      }
    },
  });

  chatErrors.add(!ok);
  chatDuration.add(res.timings.duration);
  if (res.status === 0) timeouts.add(1);
  if (res.status === 429) rateLimited.add(1);
  if (res.status >= 500) serverErrors.add(1);

  // Think time: simulates a human reading the answer before asking again.
  sleep(Math.random() * 2 + 1);
}
