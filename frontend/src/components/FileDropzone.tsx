import { useRef, useState } from 'react'
import { UploadCloud, FileSpreadsheet, Loader2 } from 'lucide-react'

interface Props {
  onFile: (file: File) => void
  loading?: boolean
}

const ALLOWED = ['.xls', '.xlsx', '.csv']
const MAX_MB = 10

export default function FileDropzone({ onFile, loading }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const validateAndSend = (file?: File) => {
    if (!file) return
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!ALLOWED.includes(ext)) {
      setError(`Định dạng không hỗ trợ. Vui lòng chọn file ${ALLOWED.join(', ')}`)
      return
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      setError(`File quá lớn (tối đa ${MAX_MB}MB)`)
      return
    }
    setError(null)
    onFile(file)
  }

  return (
    <div>
      <div
        onClick={() => !loading && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setIsDragging(false)
          if (!loading) validateAndSend(e.dataTransfer.files[0])
        }}
        className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed p-12 text-center transition
          ${isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-white hover:border-blue-400 hover:bg-gray-50'}
          ${loading ? 'cursor-wait opacity-60' : ''}`}
      >
        {loading ? (
          <>
            <Loader2 className="h-12 w-12 animate-spin text-blue-500" />
            <p className="font-medium text-gray-700">Đang đọc và phân tích file...</p>
          </>
        ) : (
          <>
            {isDragging ? (
              <FileSpreadsheet className="h-12 w-12 text-blue-500" />
            ) : (
              <UploadCloud className="h-12 w-12 text-gray-400" />
            )}
            <p className="font-medium text-gray-700">
              {isDragging ? 'Thả file vào đây' : 'Kéo thả file thời khóa biểu vào đây'}
            </p>
            <p className="text-sm text-gray-500">hoặc bấm để chọn file ({ALLOWED.join(', ')})</p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept={ALLOWED.join(',')}
          hidden
          onChange={(e) => {
            validateAndSend(e.target.files?.[0])
            e.target.value = ''
          }}
        />
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  )
}