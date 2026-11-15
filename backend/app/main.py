from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.preferences import router as preferences_router
from app.config import settings
"""
Smart Timetable Scheduler - Backend entry point.

Chạy server (từ thư mục backend/):
    uvicorn app.main:app --reload
"""
# ---------- Khởi tạo ứng dụng ----------
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Backend của hệ thống hỗ trợ sinh viên tự động tạo thời khóa biểu. "
        "Chức năng: tiếp nhận file TKB Excel/CSV, chuẩn hóa dữ liệu, "
        "phân tích sở thích và tối ưu hóa bằng Google OR-Tools CP-SAT."
    ),
    version=settings.PROJECT_VERSION,
    docs_url="/docs",    # Swagger UI
    redoc_url="/redoc",  # ReDoc
    debug=settings.DEBUG,
)

# ---------- CORS cho Frontend React/Next.js ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(preferences_router)

# ---------- Route hệ thống ----------
@app.get("/", tags=["System"], summary="Kiểm tra trạng thái server")
async def root() -> dict[str, str]:
    return {
        "message": "Smart Timetable Scheduler Backend is running",
        "status": "success",
        "version": settings.PROJECT_VERSION,
    }


@app.get("/health", tags=["System"], summary="Health check")
async def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": "backend",
    }
