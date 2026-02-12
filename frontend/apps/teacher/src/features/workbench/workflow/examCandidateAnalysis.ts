import type {
  ExamScoreSchemaSubjectCandidate,
  ExamScoreSchemaSubjectCandidateSummary,
} from '../../../appTypes'

export type ExamConflictLevel = 'strict' | 'standard' | 'lenient'
export type CandidateSummarySort = 'quality' | 'parsed_rate' | 'source_rank'

export type ParsedCandidateSummary = {
  candidateId: string
  rowsConsidered: number
  rowsParsed: number
  rowsInvalid: number
  parsedRate: number
  sourceRank: number
  qualityScore: number
  files: string[]
  types: string[]
}

export type RecommendedCandidate = {
  candidate: ExamScoreSchemaSubjectCandidate
  candidateId: string
  rowsConsidered: number
  rowsParsed: number
  rowsInvalid: number
  parseRate: number
  candidateType: string
  score: number
} | null

export type ConflictStudent = {
  studentId: string
  studentName: string
  minScore: number
  maxScore: number
  spread: number
  entries: Array<{ candidateId: string; score: number }>
}

export function getExamConflictThreshold(level: ExamConflictLevel): number {
  if (level === 'strict') return 25
  if (level === 'lenient') return 8
  return 15
}

export function getExamConflictLevelLabel(level: ExamConflictLevel): string {
  if (level === 'strict') return '严格'
  if (level === 'lenient') return '宽松'
  return '标准'
}

export function sortCandidateSummaries(
  examCandidateSummaries: ExamScoreSchemaSubjectCandidateSummary[],
  candidateSummarySort: CandidateSummarySort,
  candidateSummaryTopOnly: boolean,
): ParsedCandidateSummary[] {
  if (!examCandidateSummaries.length) return []
  const items = examCandidateSummaries
    .map((item: ExamScoreSchemaSubjectCandidateSummary) => {
      const candidateId = String(item?.candidate_id || '').trim()
      const rowsConsidered = Number(item?.rows_considered || 0)
      const rowsParsed = Number(item?.rows_parsed || 0)
      const rowsInvalid = Number(item?.rows_invalid || 0)
      const parsedRate = Number(item?.parsed_rate || 0)
      const sourceRank = Number(item?.source_rank || 99)
      const qualityScore = Number(item?.quality_score || 0)
      const files = Array.isArray(item?.files)
        ? item.files.filter(Boolean).map((x) => String(x))
        : []
      const types = Array.isArray(item?.types)
        ? item.types.filter(Boolean).map((x) => String(x))
        : []
      return {
        candidateId,
        rowsConsidered,
        rowsParsed,
        rowsInvalid,
        parsedRate,
        sourceRank,
        qualityScore,
        files,
        types,
      }
    })
    .filter((item) => Boolean(item.candidateId))

  const sorted = [...items].sort((a, b) => {
    if (candidateSummarySort === 'parsed_rate') {
      return (
        b.parsedRate - a.parsedRate
        || b.rowsParsed - a.rowsParsed
        || a.sourceRank - b.sourceRank
        || b.qualityScore - a.qualityScore
        || a.candidateId.localeCompare(b.candidateId)
      )
    }
    if (candidateSummarySort === 'source_rank') {
      return (
        a.sourceRank - b.sourceRank
        || b.qualityScore - a.qualityScore
        || b.parsedRate - a.parsedRate
        || b.rowsParsed - a.rowsParsed
        || a.candidateId.localeCompare(b.candidateId)
      )
    }
    return (
      b.qualityScore - a.qualityScore
      || b.parsedRate - a.parsedRate
      || b.rowsParsed - a.rowsParsed
      || a.sourceRank - b.sourceRank
      || a.candidateId.localeCompare(b.candidateId)
    )
  })
  return candidateSummaryTopOnly ? sorted.slice(0, 3) : sorted
}

export function computeRecommendedCandidate(
  examCandidateColumns: ExamScoreSchemaSubjectCandidate[],
  examRecommendedCandidateId: string,
): RecommendedCandidate {
  if (examRecommendedCandidateId) {
    const matched = examCandidateColumns.find(
      (candidate: ExamScoreSchemaSubjectCandidate) =>
        String(candidate?.candidate_id || '') === examRecommendedCandidateId,
    )
    if (matched) {
      const rowsConsidered = Number(matched?.rows_considered || 0)
      const rowsParsed = Number(matched?.rows_parsed || 0)
      const rowsInvalid = Number(matched?.rows_invalid || 0)
      const parseRate = rowsConsidered > 0 ? rowsParsed / rowsConsidered : 0
      return {
        candidate: matched,
        candidateId: examRecommendedCandidateId,
        rowsConsidered,
        rowsParsed,
        rowsInvalid,
        parseRate,
        candidateType: String(matched?.type || ''),
        score: Number.POSITIVE_INFINITY,
      }
    }
  }
  if (!examCandidateColumns.length) return null
  const typeWeight = (value: string) => {
    if (value === 'subject_pair') return 30
    if (value === 'direct_physics') return 20
    if (value === 'chaos_text_scan') return 6
    return 0
  }
  const sorted = [...examCandidateColumns]
    .map((candidate: ExamScoreSchemaSubjectCandidate) => {
      const rowsConsidered = Number(candidate?.rows_considered || 0)
      const rowsParsed = Number(candidate?.rows_parsed || 0)
      const rowsInvalid = Number(candidate?.rows_invalid || 0)
      const parseRate = rowsConsidered > 0 ? rowsParsed / rowsConsidered : 0
      const candidateType = String(candidate?.type || '')
      const score = (rowsParsed * 100) + (parseRate * 40) - (rowsInvalid * 12) + typeWeight(candidateType)
      return {
        candidate,
        candidateId: String(candidate?.candidate_id || ''),
        rowsConsidered,
        rowsParsed,
        rowsInvalid,
        parseRate,
        candidateType,
        score,
      }
    })
    .filter((item) => item.candidateId)
    .sort((a, b) => b.score - a.score || b.rowsParsed - a.rowsParsed || a.rowsInvalid - b.rowsInvalid)
  return sorted[0] || null
}

export function computeConflictStudents(
  examCandidateColumns: ExamScoreSchemaSubjectCandidate[],
  examConflictThreshold: number,
): ConflictStudent[] {
  if (!examCandidateColumns.length) return []
  const byStudent = new Map<string, { studentId: string; studentName: string; entries: Array<{ candidateId: string; score: number }> }>()
  for (const candidate of examCandidateColumns) {
    const candidateId = String(candidate?.candidate_id || '')
    if (!candidateId) continue
    const samples = Array.isArray(candidate?.sample_rows) ? candidate.sample_rows : []
    for (const row of samples) {
      if (!row || row?.status !== 'parsed') continue
      const scoreRaw = Number(row?.score)
      if (!Number.isFinite(scoreRaw)) continue
      const studentId = String(row?.student_id || '').trim()
      const studentName = String(row?.student_name || '').trim()
      const key = studentId || studentName
      if (!key) continue
      const bucket = byStudent.get(key) || { studentId, studentName, entries: [] }
      bucket.entries.push({ candidateId, score: scoreRaw })
      byStudent.set(key, bucket)
    }
  }
  const conflicts: ConflictStudent[] = []
  for (const item of byStudent.values()) {
    const uniqueEntries: Array<{ candidateId: string; score: number }> = []
    const seenCandidates = new Set<string>()
    for (const entry of item.entries) {
      if (!entry.candidateId || seenCandidates.has(entry.candidateId)) continue
      seenCandidates.add(entry.candidateId)
      uniqueEntries.push(entry)
    }
    if (uniqueEntries.length < 2) continue
    const scores = uniqueEntries.map((entry) => entry.score)
    const minScore = Math.min(...scores)
    const maxScore = Math.max(...scores)
    const spread = maxScore - minScore
    if (spread < examConflictThreshold) continue
    conflicts.push({
      studentId: item.studentId,
      studentName: item.studentName,
      minScore,
      maxScore,
      spread,
      entries: uniqueEntries.sort((a, b) => b.score - a.score),
    })
  }
  return conflicts.sort((a, b) => b.spread - a.spread).slice(0, 8)
}
