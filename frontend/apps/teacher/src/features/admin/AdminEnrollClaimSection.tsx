import { useCallback, useEffect, useId, useState } from 'react'

import { adminJsonHeaders, errorDetail, toText } from './adminSchoolApi'

type TeacherItem = { teacher_id?: string; teacher_name?: string }
type SubjectItem = { subject_id?: string; display_name?: string }
type OrphanItem = { assignment_id?: string; subject_id?: string; teacher_id?: string }

const ENROLL_ERRORS: Record<string, string> = {
  roster_required: '该班该科还没有任教记录，请先加任教。',
  empty_class: '该班还没有 student_auth 学生，请先导入名册。',
  class_already_owned: '该班该科已有其他教师任教。',
  teacher_not_found: '教师不存在。',
  subject_not_found: '学科不存在。',
}

export default function AdminEnrollClaimSection({
  apiBase,
  teachers,
}: {
  apiBase: string
  teachers: TeacherItem[]
}) {
  const formId = useId()
  const teacherId = `${formId}-teacher`
  const subjectId = `${formId}-subject`
  const classId = `${formId}-class`
  const [subjects, setSubjects] = useState<SubjectItem[]>([])
  const [orphans, setOrphans] = useState<OrphanItem[]>([])
  const [teacher, setTeacher] = useState('')
  const [subject, setSubject] = useState('')
  const [className, setClassName] = useState('')
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [busy, setBusy] = useState(false)

  const loadMeta = useCallback(async () => {
    try {
      const [subjectRes, orphanRes] = await Promise.all([
        fetch(`${apiBase}/auth/admin/subjects`, { headers: adminJsonHeaders() }),
        fetch(`${apiBase}/auth/admin/assignments/orphans`, { headers: adminJsonHeaders() }),
      ])
      const subjectData = (await subjectRes.json()) as { items?: SubjectItem[] }
      const orphanData = (await orphanRes.json()) as { items?: OrphanItem[] }
      if (subjectRes.ok) setSubjects(Array.isArray(subjectData.items) ? subjectData.items : [])
      if (orphanRes.ok) setOrphans(Array.isArray(orphanData.items) ? orphanData.items : [])
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载任教数据失败')
    }
  }, [apiBase])

  useEffect(() => {
    void loadMeta()
  }, [loadMeta])

  useEffect(() => {
    if (!teacher && teachers[0]?.teacher_id) setTeacher(toText(teachers[0].teacher_id))
  }, [teacher, teachers])

  useEffect(() => {
    if (!subject && subjects[0]?.subject_id) setSubject(toText(subjects[0].subject_id))
  }, [subject, subjects])

  const postJson = async (path: string, body: Record<string, string>) => {
    const res = await fetch(`${apiBase}${path}`, {
      method: 'POST',
      headers: adminJsonHeaders(),
      body: JSON.stringify(body),
    })
    const data = (await res.json()) as { ok?: boolean; detail?: string; error?: string; message?: string }
    if (!res.ok || data.ok === false) {
      const code = toText(data.detail || data.error)
      throw new Error(ENROLL_ERRORS[code] || errorDetail(data, '操作失败。'))
    }
    return data
  }

  const requireTriple = () => {
    if (!teacher || !subject || !className.trim()) {
      setError('请选择教师、学科并填写班级。')
      return false
    }
    return true
  }

  const handleRoster = async () => {
    if (!requireTriple()) return
    setError('')
    setInfo('')
    setBusy(true)
    try {
      await postJson('/auth/admin/roster', {
        teacher_id: teacher,
        subject_id: subject,
        class_name: className.trim(),
      })
      setInfo('已加任教。')
    } catch (err) {
      setError(err instanceof Error ? err.message : '加任教失败')
    } finally {
      setBusy(false)
    }
  }

  const handleEnrollClass = async () => {
    if (!requireTriple()) return
    setError('')
    setInfo('')
    setBusy(true)
    try {
      await postJson('/auth/admin/enrollments/enroll-class', {
        teacher_id: teacher,
        subject_id: subject,
        class_name: className.trim(),
      })
      setInfo('已整班入学。')
    } catch (err) {
      setError(err instanceof Error ? err.message : '整班入学失败')
    } finally {
      setBusy(false)
    }
  }

  const handleClaim = async (assignmentId: string) => {
    if (!teacher || !subject) {
      setError('认领前请选择教师和学科。')
      return
    }
    setError('')
    setInfo('')
    setBusy(true)
    try {
      await postJson(`/auth/admin/assignments/${encodeURIComponent(assignmentId)}/claim`, {
        teacher_id: teacher,
        subject_id: subject,
      })
      setInfo(`已认领 ${assignmentId}。`)
      await loadMeta()
    } catch (err) {
      setError(err instanceof Error ? err.message : '认领失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid gap-3 rounded-2xl border border-border p-4">
      <div className="text-sm font-semibold">任教、整班入学与孤儿作业</div>
      <div className="text-xs text-muted">导入名册后先加任教，再整班入学。不要指望 CSV 自动编班。</div>
      <div className="grid gap-3 md:grid-cols-3">
        <div className="grid gap-1">
          <label className="text-xs text-muted" htmlFor={teacherId}>教师</label>
          <select id={teacherId} value={teacher} onChange={(event) => setTeacher(event.target.value)}>
            <option value="">选择教师</option>
            {teachers.map((item) => {
              const id = toText(item.teacher_id)
              return <option key={id} value={id}>{toText(item.teacher_name) || id}</option>
            })}
          </select>
        </div>
        <div className="grid gap-1">
          <label className="text-xs text-muted" htmlFor={subjectId}>学科</label>
          <select id={subjectId} value={subject} onChange={(event) => setSubject(event.target.value)}>
            <option value="">选择学科</option>
            {subjects.map((item) => {
              const id = toText(item.subject_id)
              return <option key={id} value={id}>{toText(item.display_name) || id}</option>
            })}
          </select>
        </div>
        <div className="grid gap-1">
          <label className="text-xs text-muted" htmlFor={classId}>班级</label>
          <input id={classId} value={className} onChange={(event) => setClassName(event.target.value)} />
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="ghost" onClick={() => void handleRoster()} disabled={busy}>加任教</button>
        <button type="button" className="ghost" onClick={() => void handleEnrollClass()} disabled={busy}>整班入学</button>
      </div>
      {error ? <div className="status err">{error}</div> : null}
      {info ? <div className="status ok">{info}</div> : null}
      <div className="text-sm font-semibold">孤儿作业</div>
      {orphans.length ? (
        <div className="grid gap-2">
          {orphans.map((item) => {
            const assignmentId = toText(item.assignment_id)
            return (
              <div key={assignmentId} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border px-3 py-2">
                <div className="text-sm font-mono break-all">{assignmentId}</div>
                <button type="button" className="ghost" onClick={() => void handleClaim(assignmentId)} disabled={busy}>
                  认领给当前教师
                </button>
              </div>
            )
          })}
        </div>
      ) : (
        <div className="text-xs text-muted">暂无孤儿作业。</div>
      )}
    </div>
  )
}
