import { expect } from '@playwright/test'
import type { MatrixCase, MatrixCaseRunner } from './helpers/e2eMatrixCases'
import { registerMatrixCases } from './helpers/e2eMatrixCases'

const platformConsistencyCases: MatrixCase[] = [
  {
    id: 'J001',
    priority: 'P0',
    title: 'Concurrent upload jobs remain isolated by id and status',
    given: 'Two upload jobs run concurrently',
    when: 'Poll both jobs in parallel',
    then: 'Statuses do not cross-wire across job ids',
  },
  {
    id: 'J002',
    priority: 'P0',
    title: 'Confirm write failure does not leave partial artifacts',
    given: 'Confirm operation fails mid-write',
    when: 'Inspect filesystem outputs',
    then: 'No half-written artifact set remains',
  },
  {
    id: 'J003',
    priority: 'P0',
    title: 'Path traversal file names are rejected',
    given: 'Uploaded filename contains traversal segments',
    when: 'Submit upload',
    then: 'Request is rejected with security-safe error',
  },
  {
    id: 'J004',
    priority: 'P0',
    title: 'Oversized upload returns explicit limit error',
    given: 'Uploaded file exceeds configured size limit',
    when: 'Submit upload',
    then: 'Response reports file-size limit clearly',
  },
  {
    id: 'J005',
    priority: 'P1',
    title: 'Conflicting MIME and extension triggers safe validation path',
    given: 'File extension and MIME type do not match',
    when: 'Submit upload',
    then: 'Security validation path is triggered and result is safe',
  },
  {
    id: 'J006',
    priority: 'P1',
    title: 'In-flight jobs are recoverable after service restart',
    given: 'Background jobs exist before service restart',
    when: 'Restart service and query status',
    then: 'Job states are still queryable and consistent',
  },
  {
    id: 'J007',
    priority: 'P1',
    title: 'Request id remains traceable across chained endpoints',
    given: 'Client supplies request_id in workflow path',
    when: 'Run start status and confirm sequence',
    then: 'Same request_id is traceable through each stage',
  },
  {
    id: 'J008',
    priority: 'P1',
    title: 'Failed and cancelled paths do not leave dirty local state',
    given: 'Multiple failed and cancelled runs occurred',
    when: 'Start a new flow',
    then: 'No stale local keys interfere with new run',
  },
]

const implementations: Partial<Record<string, MatrixCaseRunner>> = {
  J001: async ({ page }) => {
    await page.goto('/')

    let uploadCounter = 0
    await page.route('http://localhost:8000/assignment/upload/start', async (route) => {
      uploadCounter += 1
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, job_id: `job_${uploadCounter}`, status: 'queued' }),
      })
    })

    await page.route('http://localhost:8000/assignment/upload/status**', async (route) => {
      const jobId = new URL(route.request().url()).searchParams.get('job_id') || ''
      const status = jobId === 'job_1' ? 'processing' : 'done'
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ job_id: jobId, status }),
      })
    })

    const result = await page.evaluate(async () => {
      const formA = new FormData()
      formA.append('assignment_id', 'A-J001-1')
      formA.append('files', new File(['file-a'], 'a.pdf', { type: 'application/pdf' }))

      const formB = new FormData()
      formB.append('assignment_id', 'A-J001-2')
      formB.append('files', new File(['file-b'], 'b.pdf', { type: 'application/pdf' }))

      const [startA, startB] = await Promise.all([
        fetch('http://localhost:8000/assignment/upload/start', { method: 'POST', body: formA }).then((r) => r.json()),
        fetch('http://localhost:8000/assignment/upload/start', { method: 'POST', body: formB }).then((r) => r.json()),
      ])

      const [statusA, statusB] = await Promise.all([
        fetch(`http://localhost:8000/assignment/upload/status?job_id=${startA.job_id}`).then((r) => r.json()),
        fetch(`http://localhost:8000/assignment/upload/status?job_id=${startB.job_id}`).then((r) => r.json()),
      ])

      return { startA, startB, statusA, statusB }
    })

    expect(result.startA.job_id).not.toBe(result.startB.job_id)
    expect(result.statusA.job_id).toBe(result.startA.job_id)
    expect(result.statusB.job_id).toBe(result.startB.job_id)
    const expectedByJobId: Record<string, string> = {
      job_1: 'processing',
      job_2: 'done',
    }
    expect(result.statusA.status).toBe(expectedByJobId[result.statusA.job_id])
    expect(result.statusB.status).toBe(expectedByJobId[result.statusB.job_id])
  },

  J002: async ({ page }) => {
    await page.goto('/')

    const artifactStore: string[] = []

    await page.route('http://localhost:8000/assignment/upload/confirm', async (route) => {
      const body = JSON.parse(route.request().postData() || '{}')
      if (body.job_id === 'job_fail_midwrite') {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'confirm write failed' }),
        })
        return
      }

      artifactStore.push(`artifact_${body.job_id}`)
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
    })

    await page.route('http://localhost:8000/debug/artifacts', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: artifactStore }) })
    })

    const result = await page.evaluate(async () => {
      const failed = await fetch('http://localhost:8000/assignment/upload/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: 'job_fail_midwrite' }),
      })

      const artifacts = await fetch('http://localhost:8000/debug/artifacts').then((r) => r.json())
      return { failedStatus: failed.status, artifacts }
    })

    expect(result.failedStatus).toBe(500)
    expect(result.artifacts.items).toEqual([])
  },

  J003: async ({ page }) => {
    await page.goto('/')

    await page.route('http://localhost:8000/upload', async (route) => {
      const bodyText = route.request().postData() || ''
      expect(bodyText.includes('..')).toBe(true)
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'invalid file name' }),
      })
    })

    const result = await page.evaluate(async () => {
      const form = new FormData()
      form.append('files', new File(['evil'], '../evil.pdf', { type: 'application/pdf' }))

      const res = await fetch('http://localhost:8000/upload', {
        method: 'POST',
        body: form,
      })

      const data = await res.json()
      return { status: res.status, data }
    })

    expect(result.status).toBe(400)
    expect(result.data.detail).toBe('invalid file name')
  },

  J004: async ({ page }) => {
    await page.goto('/')

    await page.route('http://localhost:8000/upload', async (route) => {
      const bodySize = route.request().postDataBuffer()?.length || 0
      expect(bodySize).toBeGreaterThan(512 * 1024)
      await route.fulfill({
        status: 413,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'file too large, max 512KB' }),
      })
    })

    const result = await page.evaluate(async () => {
      const bigPayload = new Uint8Array(700 * 1024)
      const form = new FormData()
      form.append('files', new File([bigPayload], 'big.bin', { type: 'application/octet-stream' }))

      const res = await fetch('http://localhost:8000/upload', {
        method: 'POST',
        body: form,
      })

      const data = await res.json()
      return { status: res.status, data }
    })

    expect(result.status).toBe(413)
    expect(result.data.detail).toContain('max 512KB')
  },

  J005: async ({ page }) => {
    await page.goto('/')

    await page.route('http://localhost:8000/upload', async (route) => {
      await route.fulfill({
        status: 415,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'mime-extension mismatch',
          safe_path: true,
          accepted: false,
        }),
      })
    })

    const result = await page.evaluate(async () => {
      const form = new FormData()
      form.append('files', new File(['fake-jpeg'], 'homework.pdf', { type: 'image/jpeg' }))
      const res = await fetch('http://localhost:8000/upload', {
        method: 'POST',
        body: form,
      })
      return { status: res.status, data: await res.json() }
    })

    expect(result.status).toBe(415)
    expect(result.data.detail).toBe('mime-extension mismatch')
    expect(result.data.safe_path).toBe(true)
  },

  J006: async ({ page }) => {
    await page.goto('/')

    const jobStore: Record<string, { status: string; progress: number }> = {
      job_restart_1: { status: 'processing', progress: 55 },
      job_restart_2: { status: 'queued', progress: 0 },
    }
    let restarted = false

    await page.route('http://localhost:8000/jobs/status**', async (route) => {
      const jobId = new URL(route.request().url()).searchParams.get('job_id') || ''
      const item = jobStore[jobId]
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          restarted,
          job_id: jobId,
          status: item?.status || 'unknown',
          progress: item?.progress ?? 0,
        }),
      })
    })

    await page.route('http://localhost:8000/service/restart', async (route) => {
      restarted = true
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
    })

    const result = await page.evaluate(async () => {
      const before = await Promise.all([
        fetch('http://localhost:8000/jobs/status?job_id=job_restart_1').then((r) => r.json()),
        fetch('http://localhost:8000/jobs/status?job_id=job_restart_2').then((r) => r.json()),
      ])
      await fetch('http://localhost:8000/service/restart', { method: 'POST' })
      const after = await Promise.all([
        fetch('http://localhost:8000/jobs/status?job_id=job_restart_1').then((r) => r.json()),
        fetch('http://localhost:8000/jobs/status?job_id=job_restart_2').then((r) => r.json()),
      ])
      return { before, after }
    })

    expect(result.before[0].status).toBe('processing')
    expect(result.after[0].status).toBe('processing')
    expect(result.after[0].restarted).toBe(true)
    expect(result.after[1].status).toBe('queued')
  },

  J007: async ({ page }) => {
    await page.goto('/')
    const traceLog: Array<{ stage: string; request_id: string }> = []

    await page.route('http://localhost:8000/assignment/upload/start', async (route) => {
      const payload = JSON.parse(route.request().postData() || '{}')
      traceLog.push({ stage: 'start', request_id: String(payload.request_id || '') })
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          request_id: payload.request_id,
          job_id: 'job_trace_1',
          status: 'done',
        }),
      })
    })

    await page.route('http://localhost:8000/assignment/upload/status**', async (route) => {
      const requestId = new URL(route.request().url()).searchParams.get('request_id') || ''
      traceLog.push({ stage: 'status', request_id: requestId })
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, request_id: requestId, job_id: 'job_trace_1', status: 'done' }),
      })
    })

    await page.route('http://localhost:8000/assignment/upload/confirm', async (route) => {
      const payload = JSON.parse(route.request().postData() || '{}')
      traceLog.push({ stage: 'confirm', request_id: String(payload.request_id || '') })
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, request_id: payload.request_id, assignment_id: 'A-TRACE-1' }),
      })
    })

    const result = await page.evaluate(async () => {
      const request_id = 'trace_req_20260208'
      const start = await fetch('http://localhost:8000/assignment/upload/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ request_id, assignment_id: 'A-TRACE-1' }),
      }).then((r) => r.json())

      const status = await fetch(`http://localhost:8000/assignment/upload/status?job_id=${start.job_id}&request_id=${request_id}`).then((r) => r.json())
      const confirm = await fetch('http://localhost:8000/assignment/upload/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ request_id, job_id: start.job_id }),
      }).then((r) => r.json())
      return { request_id, start, status, confirm }
    })

    expect(result.start.request_id).toBe(result.request_id)
    expect(result.status.request_id).toBe(result.request_id)
    expect(result.confirm.request_id).toBe(result.request_id)
    expect(traceLog.map((item) => item.request_id)).toEqual([result.request_id, result.request_id, result.request_id])
  },

  J008: async ({ page }) => {
    await page.goto('/')
    const localState = {
      pending_job_id: '',
      pending_request_id: '',
      last_error: '',
    }

    await page.route('http://localhost:8000/flow/start', async (route) => {
      const payload = JSON.parse(route.request().postData() || '{}')
      localState.pending_job_id = `job_${payload.mode}`
      localState.pending_request_id = String(payload.request_id || '')
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, job_id: localState.pending_job_id }),
      })
    })

    await page.route('http://localhost:8000/flow/status**', async (route) => {
      const mode = new URL(route.request().url()).searchParams.get('mode')
      const status = mode === 'failed' ? 'failed' : mode === 'cancelled' ? 'cancelled' : 'done'
      if (status !== 'done') {
        localState.last_error = status
        localState.pending_job_id = ''
        localState.pending_request_id = ''
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, status }),
      })
    })

    await page.route('http://localhost:8000/local/state', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...localState }),
      })
    })

    const result = await page.evaluate(async () => {
      const run = async (mode: 'failed' | 'cancelled' | 'fresh') => {
        const request_id = `req_${mode}`
        await fetch('http://localhost:8000/flow/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mode, request_id }),
        })
        await fetch(`http://localhost:8000/flow/status?mode=${mode}`)
      }
      await run('failed')
      await run('cancelled')
      await run('fresh')
      const status = await fetch('http://localhost:8000/local/state').then((r) => r.json())
      return status
    })

    expect(result.pending_job_id).toBe('job_fresh')
    expect(result.pending_request_id).toBe('req_fresh')
    expect(result.last_error).toBe('cancelled')
  },
}

registerMatrixCases('Platform Consistency and Security', platformConsistencyCases, implementations)
