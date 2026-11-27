"""Kiểm thử luồng upload -> confirm -> lưu DB -> đọc lại (SQLite tạm, không đụng DB thật)."""

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="tkb_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["UPLOAD_DIR"] = f"{_TMP}/uploads"
os.environ["MAX_UPLOAD_MB"] = "1"

import io  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from openpyxl import Workbook  # noqa: E402

from app.api.upload import router  # noqa: E402
from app.db.session import init_db  # noqa: E402

app = FastAPI()
app.include_router(router)

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
HEADERS = ["STT", "Mã HP", "Tên học phần", "Mã LHP", "Thứ", "Tiết", "Phòng", "Giảng viên"]
ROWS = [
    [1, "INT1001", "Nhập môn lập trình", "INT1001_01", "Thứ 2", "1-3", "A101", "Nguyễn Văn A"],
    [2, "INT1001", "Nhập môn lập trình", "INT1001_01.1", "Thứ 4", "7-8", "LAB2", "Nguyễn Văn A"],
    [3, "INT1001", "Nhập môn lập trình", "INT1001_02", "Thứ 3", "7-9", "A102", "Lê Văn C"],
    [4, "MAT1002", "Giải tích 1", "MAT1002_01", "Thứ 3, 5", "1-2", "B203", "Trần Thị B"],
]


@pytest.fixture(scope="module", autouse=True)
def _db():
    init_db()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def make_xlsx(rows=ROWS, headers=HEADERS, title_rows=1) -> bytes:
    wb = Workbook()
    ws = wb.active
    for i in range(title_rows):
        ws.append([f"Thời khóa biểu học kỳ 1 ({i})"])
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def upload(client, data: bytes, name="tkb.xlsx", ctype=XLSX):
    return client.post("/api/upload", files={"file": (name, data, ctype)})


def test_upload_suggests_mapping(client):
    res = upload(client, make_xlsx())
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "needs_confirmation"
    assert body["header_row"] == 1  # dòng 0 là tiêu đề bảng
    assert body["headers"] == HEADERS
    assert body["mapping"]["course_id"] == "Mã HP"
    assert body["mapping"]["section_id"] == "Mã LHP"
    assert body["mapping"]["weekday"] == "Thứ"
    assert body["mapping"]["time"] == "Tiết"
    assert len(body["preview"]) == 4
    assert all(len(r) == len(HEADERS) for r in body["preview"])
    # file được lưu bằng tên server tạo
    saved = list(Path(os.environ["UPLOAD_DIR"]).glob(f"{body['file_id']}.*"))
    assert len(saved) == 1


def test_confirm_save_and_read_back(client):
    up = upload(client, make_xlsx()).json()
    res = client.post(
        "/api/upload/confirm",
        json={"file_id": up["file_id"], "mapping": up["mapping"], "semester": "HK1"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "ready"
    assert body["stats"]["courses"] == 2
    assert body["stats"]["sections"] == 4
    # "Thứ 3, 5" tách thành 2 buổi
    assert body["stats"]["meetings"] == 5

    saved = client.get(f"/api/upload/{up['file_id']}/timetable")
    assert saved.status_code == 200
    # Dữ liệu đọc từ DB phải giống hệt dữ liệu vừa chuẩn hóa
    assert saved.json() == body["timetable"]
    assert saved.json()["semester"] == "HK1"

    # lớp con TH được nối với lớp cha và có nhóm
    int_course = next(c for c in saved.json()["courses"] if c["course_id"] == "INT1001")
    child = next(s for s in int_course["sections"] if s["section_id"] == "INT1001_01.1")
    assert child["parent_section_id"] == "INT1001_01"
    group = next(g for g in int_course["groups"] if g["parent_section_id"] == "INT1001_01")
    assert group["child_section_ids"] == ["INT1001_01.1"]


def test_reconfirm_replaces_data(client):
    up = upload(client, make_xlsx()).json()
    payload = {"file_id": up["file_id"], "mapping": up["mapping"]}
    assert client.post("/api/upload/confirm", json=payload).status_code == 200
    assert client.post("/api/upload/confirm", json=payload).status_code == 200
    tt = client.get(f"/api/upload/{up['file_id']}/timetable").json()
    assert len(tt["courses"]) == 2  # không bị nhân đôi


def test_timetable_before_confirm_is_409(client):
    up = upload(client, make_xlsx()).json()
    assert client.get(f"/api/upload/{up['file_id']}/timetable").status_code == 409


def test_confirm_unknown_file_404(client):
    res = client.post("/api/upload/confirm", json={"file_id": "nope", "mapping": {}})
    assert res.status_code == 404


def test_confirm_bad_mapping_returns_issues(client):
    up = upload(client, make_xlsx()).json()
    mapping = {**up["mapping"], "time": "Cột không tồn tại"}
    res = client.post("/api/upload/confirm", json={"file_id": up["file_id"], "mapping": mapping})
    assert res.status_code == 422
    codes = [i["code"] for i in res.json()["detail"]["issues"]]
    assert "UNKNOWN_COLUMN" in codes


def test_confirm_rejects_unknown_mapping_key(client):
    up = upload(client, make_xlsx()).json()
    res = client.post(
        "/api/upload/confirm",
        json={"file_id": up["file_id"], "mapping": {"course_code": "Mã HP"}},
    )
    assert res.status_code == 422


def test_missing_required_columns_needs_mapping(client):
    data = make_xlsx(rows=[[1, "X"]], headers=["STT", "Ghi chú"], title_rows=0)
    res = upload(client, data)
    assert res.status_code == 200
    assert res.json()["status"] == "needs_mapping"


def test_csv_upload(client):
    csv_text = "Mã HP,Tên học phần,Mã LHP,Thứ,Tiết\nINT1001,Lập trình,INT1001_01,2,1-3\n"
    up = upload(client, csv_text.encode("utf-8"), "tkb.csv", "text/csv").json()
    res = client.post("/api/upload/confirm", json={"file_id": up["file_id"], "mapping": up["mapping"]})
    assert res.status_code == 200, res.text
    assert res.json()["stats"]["meetings"] == 1


def test_rejects_bad_extension(client):
    assert upload(client, b"hello", "a.txt", "text/plain").status_code == 400


def test_rejects_empty_file(client):
    assert upload(client, b"", "a.csv", "text/csv").status_code == 400


def test_rejects_corrupt_xlsx_and_cleans_up(client):
    before = len(list(Path(os.environ["UPLOAD_DIR"]).glob("*")))
    assert upload(client, b"not a zip", "bad.xlsx").status_code == 422
    assert len(list(Path(os.environ["UPLOAD_DIR"]).glob("*"))) == before


def test_rejects_oversized_file_and_cleans_up(client):
    before = len(list(Path(os.environ["UPLOAD_DIR"]).glob("*")))
    res = upload(client, b"a,b\n" * 400_000, "big.csv", "text/csv")  # ~1.6 MB > 1 MB
    assert res.status_code == 413
    assert len(list(Path(os.environ["UPLOAD_DIR"]).glob("*"))) == before


def test_delete_removes_everything(client):
    up = upload(client, make_xlsx()).json()
    client.post("/api/upload/confirm", json={"file_id": up["file_id"], "mapping": up["mapping"]})
    assert client.delete(f"/api/upload/{up['file_id']}").status_code == 204
    assert client.get(f"/api/upload/{up['file_id']}/timetable").status_code == 404
    assert not list(Path(os.environ["UPLOAD_DIR"]).glob(f"{up['file_id']}.*"))
    assert client.delete(f"/api/upload/{up['file_id']}").status_code == 404