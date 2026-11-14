export interface FieldDef {
  key: string
  label: string
  required: boolean
  hint: string
}

export const MAPPING_FIELDS: FieldDef[] = [
  { key: 'course_code', label: 'Mã học phần', required: true, hint: '' },
  { key: 'course_name', label: 'Tên học phần', required: true, hint: '' },
  { key: 'class_code', label: 'Mã lớp học phần', required: true, hint: '' },
  { key: 'type', label: 'Loại buổi (LT/BT/TH)', required: false, hint: '' },
  { key: 'day', label: 'Thứ', required: true, hint: '' },
  { key: 'periods', label: 'Tiết học', required: true, hint: '' },
  { key: 'room', label: 'Phòng học', required: false, hint: '' },
  { key: 'lecturer', label: 'Giảng viên', required: false, hint: '' },
]