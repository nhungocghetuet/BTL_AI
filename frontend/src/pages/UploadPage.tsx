import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import FileDropzone from '../components/FileDropzone'
import MappingEditor from '../components/MappingEditor'
import { uploadFile, confirmMapping } from '../api/client'
import { getErrorMessage } from '../lib/errors'
import { useApp } from '../store/useAppStore'
import type { UploadResponse } from '../types'

type Step = 'drop' | 'map'

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
      setError(getErrorMessage(e, 'Không đọc được file. Vui lòng kiểm tra lại định dạng.'))
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
      setError(getErrorMessage(e, 'Xác nhận thất bại. Vui lòng thử lại.'))
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

  const width = step === 'map' ? 'max-w-4xl' : 'max-w-[640px]'

  return (
    <div className="bg-deep relative min-h-screen">
      <span className="absolute left-5 top-5 rounded-full bg-white px-4 py-2 text-sm font-bold text-wedding shadow-lg">
        TKB-AI
      </span>

      <div className="flex min-h-screen flex-col items-center justify-center px-4 py-20">
        {error && (
          <div className={`mb-4 w-full ${width} rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700`}>
            {error}
          </div>
        )}

        {step === 'drop' && <FileDropzone onFile={handleFile} loading={loading} />}

        {step === 'map' && uploaded && (
          <div className="w-full max-w-4xl rounded-3xl bg-white p-6 shadow-2xl sm:p-8">
            <MappingEditor
              headers={uploaded.headers}
              mapping={mapping}
              preview={uploaded.preview}
              loading={loading}
              onChange={(field, col) => setMapping((m) => ({ ...m, [field]: col }))}
              onConfirm={handleConfirm}
              onBack={handleBack}
            />
          </div>
        )}
      </div>
    </div>
  )
}