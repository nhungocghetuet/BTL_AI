import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { AlertCircle, ArrowLeft, CalendarDays, Loader2, Wand2 } from 'lucide-react'
import { optimize } from '../api/client'
import ExplanationBox from '../components/ExplanationBox'
import PreferencePanel from '../components/PreferencePanel'
import TimetableGrid from '../components/TimetableGrid'
import { getErrorMessage } from '../lib/errors'
import { useApp } from '../store/useAppStore'

export default function PlannerPage() {
  const navigate = useNavigate()
  const courses = useApp((s) => s.courses)
  const selected = useApp((s) => s.selected)
  const constraints = useApp((s) => s.constraints)
  const options = useApp((s) => s.options)
  const stats = useApp((s) => s.stats)
  const activeIdx = useApp((s) => s.activeIdx)
  const hasRun = useApp((s) => s.hasRun)
  const loading = useApp((s) => s.loading)
  const optimizeError = useApp((s) => s.optimizeError)
  const toggleCourse = useApp((s) => s.toggleCourse)
  const selectAll = useApp((s) => s.selectAll)
  const setResult = useApp((s) => s.setResult)
  const setActiveIdx = useApp((s) => s.setActiveIdx)
  const setLoading = useApp((s) => s.setLoading)
  const setOptimizeError = useApp((s) => s.setOptimizeError)
  const reset = useApp((s) => s.reset)

  const [slow, setSlow] = useState(false)

  if (courses.length === 0) return <Navigate to="/" replace />

  const run = async () => {
    setLoading(true)
    setOptimizeError(null)
    setSlow(false)
    // Gói miễn phí của Render "ngủ" khi không có người dùng, request đầu có thể mất 30-60 giây
    const timer = setTimeout(() => setSlow(true), 8000)
    try {
      setResult(await optimize(selected, constraints, courses))
    } catch (e) {
      setOptimizeError(getErrorMessage(e, 'Không tạo được thời khóa biểu. Vui lòng thử lại.'))
    } finally {
      clearTimeout(timer)
      setSlow(false)
      setLoading(false)
    }
  }

  const active = options[activeIdx] ?? options[0]

  return (
    <div className="min-h-screen lg:grid lg:h-screen lg:grid-cols-[380px_1fr]">
      {/* ===== Cột trái: chọn môn + yêu cầu ===== */}
      <aside className="space-y-5 border-r-2 border-tranquil bg-white/70 p-4 backdrop-blur lg:overflow-y-auto">
        <button
          type="button"
          onClick={() => {
            reset()
            navigate('/')
          }}
          className="btn btn-sm"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Tải file khác
        </button>

        <section>
          <div className="mb-2 flex items-center justify-between gap-2">
            <h2 className="font-semibold text-wedding">
              Môn học ({selected.length}/{courses.length})
            </h2>
            <div className="flex gap-1.5">
              <button type="button" onClick={() => selectAll(true)} className="btn btn-sm">
                Chọn tất cả
              </button>
              <button type="button" onClick={() => selectAll(false)} className="btn btn-sm">
                Bỏ chọn
              </button>
            </div>
          </div>
          <ul className="card max-h-64 space-y-1 overflow-y-auto p-1">
            {courses.map((c) => (
              <li key={c.course_code}>
                <label className="row-hover flex cursor-pointer items-start gap-2 rounded-md p-2 text-sm">
                  <input
                    type="checkbox"
                    checked={selected.includes(c.course_code)}
                    onChange={() => toggleCourse(c.course_code)}
                    className="mt-0.5"
                  />
                  <span>
                    <span className="font-medium">{c.course_name}</span>
                    <span className="block text-xs text-ink/60">
                      {c.course_code} · {c.classes.length} lớp
                    </span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
        </section>

        <PreferencePanel />

        <button
          type="button"
          onClick={run}
          disabled={loading || selected.length === 0}
          className="btn btn-primary w-full py-2.5"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
          Tạo thời khóa biểu
        </button>
        {selected.length === 0 && <p className="text-center text-xs text-ink/60">Hãy chọn ít nhất 1 môn học.</p>}
      </aside>

      {/* ===== Cột phải: kết quả ===== */}
      <main className="space-y-4 p-4 lg:overflow-auto">
        {loading && (
          <div className="card flex flex-col items-center gap-3 p-12 text-center">
            <Loader2 className="h-10 w-10 animate-spin text-bird" />
            <p className="font-medium text-wedding">Đang tìm thời khóa biểu tốt nhất...</p>
            {slow && (
              <p className="max-w-md text-sm text-ink/70">
                Đang đánh thức máy chủ (gói miễn phí có thể mất 30–60 giây cho lần gọi đầu tiên), vui lòng chờ thêm...
              </p>
            )}
          </div>
        )}

        {!loading && optimizeError && (
          <div className="flex gap-3 rounded-xl border border-red-300 bg-red-50 p-4 text-sm text-red-700">
            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-medium">{optimizeError}</p>
              <p className="mt-1 text-red-600">
                Nếu báo không có phương án thỏa mãn: thử bỏ bớt yêu cầu bắt buộc hoặc chọn ít môn hơn.
              </p>
            </div>
          </div>
        )}

        {!loading && !optimizeError && !hasRun && (
          <div className="card flex flex-col items-center gap-2 border-dashed p-12 text-center text-ink/70">
            <CalendarDays className="h-10 w-10 text-bird" />
            <p>Chọn môn học, nhập yêu cầu (nếu có) rồi bấm "Tạo thời khóa biểu".</p>
          </div>
        )}

        {!loading && !optimizeError && hasRun && options.length === 0 && (
          <div className="rounded-xl border border-amber-300 bg-amber-50 p-6 text-center text-amber-900">
            Không có phương án nào thỏa mãn. Hãy nới bớt yêu cầu bắt buộc hoặc chọn ít môn hơn.
          </div>
        )}

        {!loading && active && (
          <>
            <div className="flex flex-wrap gap-2">
              {options.map((o, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => setActiveIdx(i)}
                  className={`btn ${i === activeIdx ? 'btn-active' : ''}`}
                >
                  Phương án {i + 1} · {o.score} điểm
                </button>
              ))}
            </div>
            <TimetableGrid sessions={active.sessions} />
            <ExplanationBox option={active} stats={stats} />
          </>
        )}
      </main>
    </div>
  )
}