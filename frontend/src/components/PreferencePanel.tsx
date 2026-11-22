import { useState } from 'react'
import { AlertCircle, Loader2, Sparkles, X } from 'lucide-react'
import { parsePreferences } from '../api/client'
import { buildChips, ISSUE_LABEL } from '../lib/constraints'
import { getErrorMessage } from '../lib/errors'
import { useApp } from '../store/useAppStore'

const SUGGESTIONS = [
  'Không học thứ 7',
  'Tránh học buổi sáng',
  'Ưu tiên nghỉ thứ 6, học dồn vào ít ngày',
  'Hạn chế tiết trống giữa các buổi',
]

export default function PreferencePanel() {
  const courses = useApp((s) => s.courses)
  const constraints = useApp((s) => s.constraints)
  const issues = useApp((s) => s.issues)
  const setParsed = useApp((s) => s.setParsed)
  const setConstraints = useApp((s) => s.setConstraints)

  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const chips = buildChips(constraints, courses)

  const analyze = async () => {
    const value = text.trim()
    if (!value || busy) return
    setBusy(true)
    setError(null)
    try {
      setParsed(await parsePreferences(value, courses))
    } catch (e) {
      setError(getErrorMessage(e, 'Không phân tích được yêu cầu. Vui lòng thử lại.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="space-y-3">
      <h2 className="flex items-center gap-2 font-semibold text-wedding">
        <Sparkles className="h-4 w-4 text-wind" /> Yêu cầu của bạn
      </h2>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) analyze()
        }}
        rows={4}
        maxLength={2000}
        placeholder="VD: Không học thứ 7, ưu tiên học buổi chiều, tránh tiết 1"
        className="field resize-none"
      />

      <div className="flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setText((t) => (t.trim() ? `${t.trim()}. ${s}` : s))}
            className="btn btn-sm"
          >
            + {s}
          </button>
        ))}
      </div>

      <button type="button" onClick={analyze} disabled={!text.trim() || busy} className="btn w-full">
        {busy && <Loader2 className="h-4 w-4 animate-spin" />}
        Phân tích yêu cầu
      </button>

      {error && <p className="rounded-lg border border-red-300 bg-red-50 p-2 text-sm text-red-700">{error}</p>}

      {issues.length > 0 && (
        <ul className="space-y-1.5 rounded-lg border border-amber-300 bg-amber-50 p-2 text-sm text-amber-900">
          {issues.map((it, i) => (
            <li key={i} className="flex gap-2">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                <b>{ISSUE_LABEL[it.code] ?? it.code}:</b> {it.message}
                {it.source_text && <i className="block text-xs opacity-80">"{it.source_text}"</i>}
              </span>
            </li>
          ))}
        </ul>
      )}

      {chips.length > 0 && (
        <div>
          <p className="mb-1.5 text-xs text-ink/70">
            Hệ thống hiểu như sau (bấm × để bỏ điều không đúng).{' '}
            <span className="rounded bg-wedding px-1.5 py-0.5 text-white">Xanh đậm: bắt buộc</span>{' '}
            <span className="rounded border border-tranquil bg-celestia px-1.5 py-0.5">Xanh nhạt: ưu tiên (mức 1–5)</span>
          </p>
          <div className="flex flex-wrap gap-1.5">
            {chips.map((c) => (
              <span
                key={c.id}
                className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs transition ${
                  c.kind === 'hard'
                    ? 'border-wedding bg-wedding text-white hover:bg-king'
                    : 'border-tranquil bg-celestia text-ink hover:bg-mint'
                }`}
              >
                {c.label}
                {c.weight !== undefined && <span className="opacity-75">(mức {c.weight}/5)</span>}
                <button
                  type="button"
                  aria-label={`Bỏ: ${c.label}`}
                  onClick={() => setConstraints(c.remove(constraints))}
                  className="rounded-full p-0.5 hover:bg-white/40"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}