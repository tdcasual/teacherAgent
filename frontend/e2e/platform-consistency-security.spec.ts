import type { MatrixCase } from './helpers/e2eMatrixCases'
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

registerMatrixCases('Platform Consistency and Security', platformConsistencyCases)
