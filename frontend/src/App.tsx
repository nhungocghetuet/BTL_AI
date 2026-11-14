import { BrowserRouter, Routes, Route } from 'react-router-dom'
import UploadPage from './pages/UploadPage'
import PlannerPage from './pages/PlannerPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/plan" element={<PlannerPage />} />
      </Routes>
    </BrowserRouter>
  )
}