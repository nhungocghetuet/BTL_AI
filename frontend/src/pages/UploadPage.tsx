import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import FileDropzone from '../components/FileDropzone'
import MappingEditor from '../components/MappingEditor'
import { uploadFile, confirmMapping } from '../api/client'
import { useApp } from '../store/useAppStore'
import type { UploadResponse } from '../types'

type Step = 'drop' | 'map'

function errMsg(e: unknown, fallback: string): string {
  if (axios.isAxiosError(e)) return e.response?.data?.detail ?? fallback
  return fallback
}

export default function UploadPage() {
  const navigate = useNavigate()
  const { setUpload, setCourses } = useApp()

  const [step, setStep] = useState<Step>('drop')
  const [uploaded, setUploaded] = useState<UploadResponse | null>(null)
  const [mapping, setMapping] = useState<Record<string, string | null>>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleFile = async (file: File) => {
    setLoading(true)
    setError(null)
    try {
      const res = await uploadFile(file)
      setUploaded(res)
      setMapping(res.mapping)
      setStep('map')
    } catch (e) {
      setError(errMsg(e, 'Không đọc được file. Vui lòng kiểm tra lại định dạng.'))
    } finally {
      setLoading(false)
    }
  }

  const handleConfirm = async () => {
    if (!uploaded) return
    setLoading(true)
    setError(null)
    try {
      const { courses } = await confirmMapping(uploaded.file_id, mapping)
      setUpload(uploaded.file_id)
      setCourses(courses)
      navigate('/plan')
    } catch (e) {
      setError(errMsg(e, 'Xác nhận thất bại. Vui lòng thử lại.'))
    } finally {
      setLoading(false)
    }
  }

  const handleBack = () => {
    setStep('drop')
    setUploaded(null)
    setMapping({})
    setError(null)
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-4xl px-4 py-10">
        <header className="mb-8 text-center">
          <h1 className="text-3xl font-bold">Xếp thời khóa biểu thông minh</h1>
          <p className="mt-2 text-gray-500">
            Tải lên file lịch học của trường, mô tả mong muốn bằng tiếng Việt, hệ thống sẽ lo phần còn lại.
          </p>
        </header>

        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>
        )}

        {step === 'drop' && <FileDropzone onFile={handleFile} loading={loading} />}

        {step === 'map' && uploaded && (
          <MappingEditor
            headers={uploaded.headers}
            mapping={mapping}
            preview={uploaded.preview}
            loading={loading}
            onChange={(field, col) => setMapping((m) => ({ ...m, [field]: col }))}
            onConfirm={handleConfirm}
            onBack={handleBack}
          />
        )}
      </div>
    </div>
  )
}