import http from 'k6/http'
import { check, sleep } from 'k6'

export const options = {
  vus: 10,
  duration: '60s',
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<1500'],
  },
}

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000'

const jsonHeaders = {
  headers: {
    'Content-Type': 'application/json',
  },
}

export default function () {
  const health = http.get(`${BASE_URL}/healthz`)
  check(health, {
    'health status 200': (r) => r.status === 200,
    'health payload ok': (r) => r.body.includes('"status":"ok"'),
  })

  const login = http.post(
    `${BASE_URL}/api/v2/auth/student/login`,
    JSON.stringify({
      student_id: 'stu-k6',
      credential: 'S-123',
    }),
    jsonHeaders,
  )
  check(login, {
    'login status 200|401': (r) => r.status === 200 || r.status === 401,
  })

  const send = http.post(
    `${BASE_URL}/api/v2/chat/send`,
    JSON.stringify({
      session_id: 'k6-session',
      message: 'k6 probe message',
    }),
    jsonHeaders,
  )
  check(send, {
    'chat send status 200|400': (r) => r.status === 200 || r.status === 400,
  })

  sleep(0.3)
}
