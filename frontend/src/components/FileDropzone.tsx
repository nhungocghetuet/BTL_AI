import { useRef, useState } from 'react'
import { UploadCloud, FileSpreadsheet, Loader2 } from 'lucide-react'

interface Props {
  /** Được gọi khi người dùng bấm nút "Tải lên" (không phải ngay khi chọn file). */
  onFile: (file: File) => void
  loading?: boolean
}

const ALLOWED = ['.xls', '.xlsx', '.csv']
const MAX_MB = 10

function formatSize(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export default function FileDropzone({ onFile, loading }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)

  const pick = (f?: File) => {
    if (!f) return
    const ext = '.' + f.name.split('.').pop()?.toLowerCase()
    if (!ALLOWED.includes(ext)) {
      setError(`Định dạng không hỗ trợ. Vui lòng chọn file ${ALLOWED.join(', ')}`)
      return
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(`File quá lớn (tối đa ${MAX_MB}MB)`)
      return
    }
    setError(null)
    setFile(f)
  }

  const openPicker = () => {
    if (!loading) inputRef.current?.click()
  }

  return (
    <div className="w-full max-w-[640px] rounded-3xl bg-white p-8 shadow-2xl">
      <h2 className="mb-5 text-xl font-bold text-ink">Tải file lên</h2>

      <div
        role="button"
        tabIndex={0}
        onClick={openPicker}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            openPicker()
          }
        }}
        onDragOver={(e) => {
          e.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setIsDragging(false)
          if (!loading) pick(e.dataTransfer.files[0])
        }}
        className={`flex h-60 flex-col items-center justify-center gap-3 rounded-xl border-2 border-bird px-4 text-center transition focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-bird ${
          isDragging ? 'border-solid bg-mint' : 'border-dashed bg-heaven/40 hover:bg-mint/60'
        } ${loading ? 'cursor-wait opacity-70' : 'cursor-pointer'}`}
      >
        {loading ? (
          <>
            <Loader2 className="h-10 w-10 animate-spin text-bird" />
            <p className="text-ink/80">Đang đọc và phân tích file...</p>
          </>
        ) : file ? (
          <>
            <FileSpreadsheet className="h-10 w-10 text-king" />
            <p className="max-w-full truncate font-semibold text-ink">{file.name}</p>
            <p className="text-sm text-ink/60">
              {formatSize(file.size)} ·{' '}
              <span className="font-medium text-king underline">Chọn file khác</span>
            </p>
          </>
        ) : (
          <>
            <UploadCloud className="h-10 w-10 text-bird" />
            <p className="text-ink/70">
              {isDragging ? (
                'Thả file vào đây'
              ) : (
                <>
                  Kéo thả file vào đây hoặc <span className="font-medium text-king underline">Chọn file</span>
                </>
              )}
            </p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept={ALLOWED.join(',')}
          hidden
          onChange={(e) => {
            pick(e.target.files?.[0])
            e.target.value = ''
          }}
        />
      </div>

      <div className="mt-3 flex flex-wrap justify-between gap-2 text-sm text-ink/60">
        <span>Định dạng hỗ trợ: XLS, XLSX, CSV</span>
        <span>Tối đa: {MAX_MB}MB</span>
      </div>

      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      <div className="mt-6 flex justify-end">
        <button type="button" disabled={!file || loading} onClick={() => file && onFile(file)} className="btn btn-primary px-6">
          {loading && <Loader2 className="h-4 w-4 animate-spin" />}
          Tải lên
        </button>
      </div>
    </div>
  )
}