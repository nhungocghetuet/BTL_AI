import { CheckCircle2, Clock, Gauge, Lightbulb, ListChecks } from 'lucide-react'
import type { OptimizeStats, TimetableOption } from '../types'

const STATUS_LABEL: Record<string, string> = {
  OPTIMAL: 'Tối ưu',
  FEASIBLE: 'Khả thi',
  MOCK: 'Dữ liệu mẫu',
}

interface Props {
  option?: TimetableOption
  stats?: OptimizeStats
}

function Tile({ label, value, icon }: { label: string; value: string | number; icon?: React.ReactNode }) {
  return (
    <div className="card card-hover p-3">
      <dt className="flex items-center gap-1 text-xs text-ink/70">
        {icon} {label}
      </dt>
      <dd className="mt-1 text-lg font-semibold text-wedding">{value}</dd>
    </div>
  )
}

export default function ExplanationBox({ option, stats }: Props) {
  if (!option) return null
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="card card-hover p-4">
        <h3 className="mb-2 flex items-center gap-2 font-semibold text-wedding">
          <Lightbulb className="h-4 w-4 text-wind" /> Vì sao chọn phương án này
        </h3>
        {option.explanation.length > 0 ? (
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {option.explanation.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-ink/60">Backend chưa trả lời giải thích cho phương án này.</p>
        )}

        <h4 className="mb-1 mt-4 flex items-center gap-2 text-sm font-semibold text-wedding">
          <ListChecks className="h-4 w-4 text-wind" /> Các lớp được chọn
        </h4>
        <ul className="flex flex-wrap gap-2 text-xs">
          {option.chosen.map((c) => (
            <li
              key={`${c.course_code}-${c.class_code}`}
              className="row-hover rounded-full border border-tranquil bg-celestia/60 px-2.5 py-1"
            >
              {c.class_code}
            </li>
          ))}
        </ul>
      </section>

      <section className="card card-hover p-4">
        <h3 className="mb-3 flex items-center gap-2 font-semibold text-wedding">
          <Gauge className="h-4 w-4 text-wind" /> Hiệu năng tính toán
        </h3>
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <Tile
            label="Thời gian giải"
            value={stats ? `${stats.solve_ms} ms` : '—'}
            icon={<Clock className="h-3 w-3" />}
          />
          <Tile
            label="Trạng thái"
            value={stats ? (STATUS_LABEL[stats.status] ?? stats.status) : '—'}
            icon={<CheckCircle2 className="h-3 w-3" />}
          />
          <Tile label="Điểm hài lòng" value={option.score} />
          <Tile label="Số biến mô hình" value={stats?.num_vars ?? '—'} />
        </dl>
      </section>
    </div>
  )
}