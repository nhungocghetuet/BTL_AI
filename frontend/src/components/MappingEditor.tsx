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
        <h2 className="text-xl font-semibold">Kiểm tra ánh xạ cột</h2>
        <p className="text-sm text-gray-500">
          Hệ thống đã tự đoán cột nào là gì. Hãy kiểm tra và sửa lại nếu có chỗ sai.
        </p>
      </div>

      <div className="divide-y rounded-xl border bg-white">
        {MAPPING_FIELDS.map((f) => {
          const value = mapping[f.key] ?? ''
          const isMissing = f.required && !value
          return (
            <div key={f.key} className="grid grid-cols-[1fr_1fr_24px] items-center gap-4 p-3">
              <div>
                <div className="font-medium">
                  {f.label} {f.required && <span className="text-red-500">*</span>}
                </div>
                {f.hint && <div className="text-xs text-gray-400">{f.hint}</div>}
              </div>
              <select
                value={value}
                onChange={(e) => onChange(f.key, e.target.value || null)}
                className={`w-full rounded-lg border px-3 py-2 text-sm ${
                  isMissing ? 'border-red-400 bg-red-50' : 'border-gray-300'
                }`}
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
                <CheckCircle2 className="h-5 w-5 text-green-500" />
              ) : (
                <span />
              )}
            </div>
          )
        })}
      </div>

      {duplicates.length > 0 && (
        <p className="text-sm text-amber-600">
          ⚠ Cột "{duplicates[0]}" đang được gán cho nhiều trường. Hãy kiểm tra lại.
        </p>
      )}

      <div>
        <h3 className="mb-2 text-sm font-medium text-gray-700">Xem trước dữ liệu</h3>
        <div className="overflow-x-auto rounded-xl border bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                {headers.map((h) => (
                  <th
                    key={h}
                    className={`whitespace-nowrap px-3 py-2 text-left font-medium ${
                      usedColumns.has(h) ? 'bg-blue-50 text-blue-700' : 'text-gray-500'
                    }`}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.map((row, i) => (
                <tr key={i} className="border-t">
                  {row.map((cell, j) => (
                    <td
                      key={j}
                      className={`whitespace-nowrap px-3 py-2 ${
                        usedColumns.has(headers[j]) ? 'bg-blue-50/40' : 'text-gray-400'
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

      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          disabled={loading}
          className="rounded-lg border px-4 py-2 text-sm hover:bg-gray-50 disabled:opacity-50"
        >
          ← Chọn file khác
        </button>
        <div className="flex items-center gap-3">
          {missing.length > 0 && (
            <span className="text-sm text-red-600">Còn thiếu: {missing.map((m) => m.label).join(', ')}</span>
          )}
          <button
            onClick={onConfirm}
            disabled={!canConfirm}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2 font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-300"
          >
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            Xác nhận và tiếp tục
          </button>
        </div>
      </div>
    </div>
  )
}