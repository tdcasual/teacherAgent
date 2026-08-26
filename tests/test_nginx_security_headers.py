from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NGINX_CONF = ROOT / "frontend" / "nginx.conf"
DOCKERFILES = (
    ROOT / "frontend" / "Dockerfile.student",
    ROOT / "frontend" / "Dockerfile.teacher",
)

# Bundled KaTeX CSS + woff2 stay same-origin under font-src 'self'.
KATEX_SAME_ORIGIN_ASSETS = (
    "katex/dist/katex.min.css",
    "KaTeX_Main-Regular.woff2",
)


def test_nginx_conf_has_csp_nosniff_and_frame_ancestors() -> None:
    text = NGINX_CONF.read_text(encoding="utf-8")
    assert "X-Content-Type-Options nosniff" in text
    assert "frame-ancestors" in text
    assert "__API_ORIGIN__" in text
    assert "font-src" in text
    assert "worker-src" in text
    assert "manifest-src" in text
    assert "X-Frame-Options DENY" in text
    assert "Referrer-Policy no-referrer" in text
    assert "connect-src https:" not in text
    assert "connect-src 'self' __API_ORIGIN__" in text


def test_student_and_teacher_dockerfiles_replace_api_origin() -> None:
    for path in DOCKERFILES:
        text = path.read_text(encoding="utf-8")
        assert "__API_ORIGIN__" in text, f"{path.name} must replace __API_ORIGIN__"
        assert "sed" in text, f"{path.name} must sed-replace the API origin placeholder"
        assert "VITE_API_URL is required" in text, f"{path.name} must fail the build if VITE_API_URL is missing"


def test_katex_css_and_woff2_are_same_origin() -> None:
    student = (ROOT / "frontend" / "apps" / "student" / "src" / "App.tsx").read_text(encoding="utf-8")
    teacher = (ROOT / "frontend" / "apps" / "teacher" / "src" / "App.tsx").read_text(encoding="utf-8")
    css_import = KATEX_SAME_ORIGIN_ASSETS[0]
    assert css_import in student
    assert css_import in teacher
    assert "cdn.jsdelivr" not in student.lower()
    assert "cdn.jsdelivr" not in teacher.lower()

    conf = NGINX_CONF.read_text(encoding="utf-8")
    assert "font-src 'self'" in conf
    assert "KaTeX_Main-Regular.woff2" in KATEX_SAME_ORIGIN_ASSETS
