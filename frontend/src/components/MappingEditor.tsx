import { CheckCircle2, AlertCircle, Loader2 } from 'lucide-react'
import { MAPPING_FIELDS } from '../constants'

interface Props {
  headers: string[]
  mapping: Record<string, string | null>
  preview: string[][]
  loading?: boolean
  onChange: (field: string, column: string | null) => void
  onConfirm: () => void
  onBack: () => void
}

export default function MappingEditor({ headers, mapping, preview, loading, onChange, onConfirm, onBack }: Props) {
  const missing = MAPPING_FIELDS.filter((f) => f.required && !mapping[f.key])
  const canConfirm = missing.length === 0 && !loading
  const usedColumns = new Set(Object.values(mapping).filter(Boolean) as string[])
  const duplicates = Object.values(mapping).filter((v, i, arr) => v && arr.indexOf(v) !== i)

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-wedding">Kiểm tra ánh xạ cột</h2>
        <p className="text-sm text-ink/70">
          Hệ thống đã tự đoán cột nào là gì. Hãy kiểm tra và sửa lại nếu có chỗ sai.
        </p>
      </div>

      <div className="card divide-y divide-celestia overflow-hidden">
        {MAPPING_FIELDS.map((f) => {
          const value = mapping[f.key] ?? ''
          const isMissing = f.required && !value
          return (
            <div key={f.key} className="row-hover grid grid-cols-[1fr_1fr_24px] items-center gap-4 p-3">
              <div>
                <div className="font-medium">
                  {f.label} {f.required && <span className="text-red-500">*</span>}
                </div>
                {f.hint && <div className="text-xs text-ink/50">{f.hint}</div>}
              </div>
              <select
                value={value}
                onChange={(e) => onChange(f.key, e.target.value || null)}
                className={`field ${isMissing ? '!border-red-400 !bg-red-50' : ''}`}
              >
                <option value="">-- Không chọn --</option>
                {headers.map((h) => (
                  <option key={h} value={h}>
                    {h}
                  </option>
                ))}
              </select>
              {isMissing ? (
                <AlertCircle className="h-5 w-5 text-red-500" />
              ) : value ? (
                <CheckCircle2 className="h-5 w-5 text-streak" />
              ) : (
                <span />
              )}
            </div>
          )
        })}
      </div>

      {duplicates.length > 0 && (
        <p className="text-sm text-amber-700">
          ⚠ Cột "{duplicates[0]}" đang được gán cho nhiều trường. Hãy kiểm tra lại.
        </p>
      )}

      <div>
        <h3 className="mb-2 text-sm font-medium text-wedding">Xem trước dữ liệu</h3>
        <div className="card overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr>
                {headers.map((h) => (
                  <th
                    key={h}
                    className={`whitespace-nowrap px-3 py-2 text-left font-semibold ${
                      usedColumns.has(h) ? 'bg-alice text-wedding' : 'bg-heaven text-ink/60'
                    }`}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.map((row, i) => (
                <tr key={i} className="row-hover border-t border-celestia">
                  {row.map((cell, j) => (
                    <td
                      key={j}
                      className={`whitespace-nowrap px-3 py-2 ${
                        usedColumns.has(headers[j]) ? 'bg-ice/70' : 'text-ink/40'
                      }`}
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <button onClick={onBack} disabled={loading} className="btn">
          ← Chọn file khác
        </button>
        <div className="flex items-center gap-3">
          {missing.length > 0 && (
            <span className="text-sm text-red-600">Còn thiếu: {missing.map((m) => m.label).join(', ')}</span>
          )}
          <button onClick={onConfirm} disabled={!canConfirm} className="btn btn-primary">
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            Xác nhận và tiếp tục
          </button>
        </div>
      </div>
    </div>
  )
}