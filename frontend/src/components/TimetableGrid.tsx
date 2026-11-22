import { useMemo } from 'react'
import { AlertTriangle } from 'lucide-react'
import type { PlacedSession } from '../types'
import { dayLabel } from '../lib/constraints'
import { COURSE_COLORS } from '../lib/palette'
import { findConflicts, layoutSessions } from '../lib/timetable'

const MIN_PERIODS = 12
const ROW_PX = 52

export default function TimetableGrid({ sessions }: { sessions: PlacedSession[] }) {
  const { placed, skipped } = useMemo(() => layoutSessions(sessions), [sessions])
  const conflicts = useMemo(() => findConflicts(sessions), [sessions])
  const conflictIdx = useMemo(() => new Set(conflicts.flatMap((c) => [c.a, c.b])), [conflicts])

  const maxPeriod = Math.max(MIN_PERIODS, ...placed.map((p) => p.end))
  const days = placed.some((p) => p.day === 8) ? [2, 3, 4, 5, 6, 7, 8] : [2, 3, 4, 5, 6, 7]
  const periods = Array.from({ length: maxPeriod }, (_, i) => i + 1)
  const courseCodes = [...new Set(sessions.map((s) => s.course_code))]
  const colorOf = (code: string) => COURSE_COLORS[courseCodes.indexOf(code) % COURSE_COLORS.length]

  return (
    <div className="space-y-3">
      {conflicts.length > 0 && (
        <div className="flex gap-2 rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <ul className="space-y-1">
            {conflicts.map((c, i) => (
              <li key={i}>
                {sessions[c.a].course_name} ({sessions[c.a].type}) trùng với {sessions[c.b].course_name} (
                {sessions[c.b].type}) vào {dayLabel(c.day)}, tiết {c.periods.join(', ')}
              </li>
            ))}
          </ul>
        </div>
      )}
      {skipped.length > 0 && (
        <p className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
          Có {skipped.length} buổi học không xác định được thứ hoặc tiết nên chưa hiển thị trên lưới:{' '}
          {skipped.map((s) => `${s.course_name} (${s.type})`).join(', ')}.
        </p>
      )}

      <div className="card overflow-x-auto">
        <div
          className="grid min-w-[720px] text-sm"
          style={{
            gridTemplateColumns: `64px repeat(${days.length}, minmax(0, 1fr))`,
            gridTemplateRows: `38px repeat(${maxPeriod}, ${ROW_PX}px)`,
          }}
        >
          <div className="bg-heaven" style={{ gridColumn: 1, gridRow: 1 }} />
          {days.map((d, i) => (
            <div
              key={d}
              className="row-hover flex items-center justify-center border-l border-celestia bg-heaven font-semibold text-wedding"
              style={{ gridColumn: i + 2, gridRow: 1 }}
            >
              {dayLabel(d)}
            </div>
          ))}

          {periods.map((p) => (
            <div
              key={`label-${p}`}
              className={`border-t bg-ice px-1 pt-1 text-xs text-ink/70 ${
                p === 7 ? 'border-t-2 border-t-king/60' : 'border-t-celestia'
              }`}
              style={{ gridColumn: 1, gridRow: p + 1 }}
            >
              <div>Tiết {p}</div>
              {p === 1 && <div className="font-semibold text-king">Sáng</div>}
              {p === 7 && <div className="font-semibold text-king">Chiều</div>}
            </div>
          ))}

          {periods.flatMap((p) =>
            days.map((d, i) => (
              <div
                key={`cell-${p}-${d}`}
                className={`row-hover border-l border-t border-l-celestia ${
                  p === 7 ? 'border-t-2 border-t-king/60' : 'border-t-celestia'
                }`}
                style={{ gridColumn: i + 2, gridRow: p + 1 }}
              />
            )),
          )}

          {placed.map((x) => {
            const s = x.session
            const bad = conflictIdx.has(x.index)
            const color = colorOf(s.course_code)
            return (
              <div
                key={x.index}
                title={`${s.course_name} (${s.course_code})\n${s.type} · ${s.class_code}\n${dayLabel(x.day)}, tiết ${x.start}${
                  x.end > x.start ? `–${x.end}` : ''
                }${s.room ? `\nPhòng ${s.room}` : ''}`}
                className={`lift z-10 m-0.5 cursor-default overflow-hidden rounded-md border p-1 text-xs leading-tight text-ink ${
                  bad ? 'ring-2 ring-red-500' : ''
                }`}
                style={{
                  backgroundColor: color.bg,
                  borderColor: bad ? '#ef4444' : color.border,
                  borderLeftWidth: 4,
                  gridColumn: days.indexOf(x.day) + 2,
                  gridRow: `${x.start + 1} / ${x.end + 2}`,
                  width: `calc(${100 / x.lanes}% - 4px)`,
                  justifySelf: 'start',
                  transform: `translateX(calc(${x.lane} * (100% + 4px)))`,
                }}
              >
                <div className="truncate font-semibold">{s.course_name}</div>
                <div className="truncate">
                  {s.type} · {s.class_code}
                </div>
                {s.room && <div className="truncate opacity-80">{s.room}</div>}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}