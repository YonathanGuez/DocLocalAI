// Isolates the LLM generation limit: hits Ollama directly, bypassing the
// FastAPI app, DB, retrieval and reranker entirely. Tells you the ceiling
// of the model/runtime itself, independent of the rest of the stack.
import http from 'k6/http';
import { check } from 'k6';
import { Trend } from 'k6/metrics';

const BASE_URL = __ENV.OLLAMA_URL || 'http://ollama:11434';
const MODEL = __ENV.MODEL || 'qwen2.5:0.5b';

const genDuration = new Trend('llm_gen_duration_ms', true);

const PROMPTS = [
  'Explain what CrashLoopBackOff means in Kubernetes in two sentences.',
  'Summarize how to debug a pod stuck in Pending state.',
  'What is the purpose of a liveness probe?',
  'List three common causes of OOMKilled pods.',
  'How would you check why a Service has no endpoints?',
];

export const options = {
  scenarios: {
    llm_concurrency: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: JSON.parse(__ENV.STAGES || JSON.stringify([
        { duration: '20s', target: 1 },
        { duration: '20s', target: 2 },
        { duration: '20s', target: 4 },
        { duration: '20s', target: 6 },
        { duration: '15s', target: 0 },
      ])),
      gracefulRampDown: '15s',
    },
  },
};

export default function () {
  const prompt = PROMPTS[Math.floor(Math.random() * PROMPTS.length)];
  const res = http.post(
    `${BASE_URL}/v1/chat/completions`,
    JSON.stringify({
      model: MODEL,
      messages: [{ role: 'user', content: prompt }],
      max_tokens: 200,
      temperature: 0.1,
    }),
    { headers: { 'Content-Type': 'application/json' }, timeout: '120s' },
  );

  check(res, { 'status is 200': (r) => r.status === 200 });
  genDuration.add(res.timings.duration);
}
