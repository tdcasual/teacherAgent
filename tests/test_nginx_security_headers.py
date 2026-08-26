import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NGINX_CONF = ROOT / "frontend" / "nginx.conf"
DOCKERFILES = (
    ROOT / "frontend" / "Dockerfile.student",
    ROOT / "frontend" / "Dockerfile.teacher",
    ROOT / "frontend" / "Dockerfile",
)
KATEX_CSS_CANDIDATES = (
    ROOT / "frontend" / "node_modules" / "katex" / "dist" / "katex.min.css",
    ROOT / "tests" / "fixtures" / "katex.min.css",
)
SED_BAKE = 'sed -i "s|__API_ORIGIN__|${API_ORIGIN}|g" /etc/nginx/conf.d/default.conf'
PLACEHOLDER_GUARD = 'if grep -qF "__API_ORIGIN__" /etc/nginx/conf.d/default.conf'


def test_nginx_conf_has_csp_nosniff_and_frame_ancestors() -> None:
    text = NGINX_CONF.read_text(encoding="utf-8")
    assert "X-Content-Type-Options nosniff" in text
    assert "X-Frame-Options DENY" in text
    assert "Referrer-Policy no-referrer" in text
    assert "img-src 'self' data: blob: __API_ORIGIN__" in text
    assert "font-src 'self'" in text
    assert "worker-src 'self'" in text
    assert "manifest-src 'self'" in text
    assert "frame-ancestors 'none'" in text
    assert "connect-src 'self' __API_ORIGIN__" in text
    assert "connect-src https:" not in text


def test_student_and_teacher_dockerfiles_replace_api_origin() -> None:
    for path in DOCKERFILES:
        text = path.read_text(encoding="utf-8")
        assert "VITE_API_URL is required" in text, f"{path.name} must fail the build if VITE_API_URL is missing"
        assert SED_BAKE in text, f"{path.name} must sed-replace __API_ORIGIN__ in default.conf"
        assert PLACEHOLDER_GUARD in text, f"{path.name} must fail if the origin placeholder remains"
        assert "chmod 644 /etc/nginx/conf.d/default.conf" in text
        sed_at = text.index(SED_BAKE)
        user_at = text.index("USER nginx")
        assert user_at > sed_at, f"{path.name} must USER nginx after baking nginx.conf"


def test_katex_css_and_woff2_are_same_origin() -> None:
    student = (ROOT / "frontend" / "apps" / "student" / "src" / "App.tsx").read_text(encoding="utf-8")
    teacher = (ROOT / "frontend" / "apps" / "teacher" / "src" / "App.tsx").read_text(encoding="utf-8")
    assert "katex/dist/katex.min.css" in student
    assert "katex/dist/katex.min.css" in teacher

    css_path = next((path for path in KATEX_CSS_CANDIDATES if path.is_file()), None)
    assert css_path is not None, "katex.min.css missing from node_modules and tests/fixtures"
    css = css_path.read_text(encoding="utf-8")
    urls = [match.group(1) for match in re.finditer(r"url\(([^)]+)\)", css)]
    assert urls, f"no url() font refs in {css_path}"
    woff2 = [url for url in urls if url.endswith(".woff2")]
    assert woff2, f"{css_path} must reference same-origin .woff2 fonts"
    assert any(url.endswith("KaTeX_Main-Regular.woff2") for url in woff2)
    for url in urls:
        assert not url.startswith(("http://", "https://", "//")), url
        assert url.startswith("fonts/"), url

    fonts_dir = ROOT / "frontend" / "node_modules" / "katex" / "dist" / "fonts"
    if fonts_dir.is_dir():
        assert (fonts_dir / "KaTeX_Main-Regular.woff2").is_file()

    conf = NGINX_CONF.read_text(encoding="utf-8")
    assert "font-src 'self'" in conf
