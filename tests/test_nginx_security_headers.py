import re
from pathlib import Path

_CSP_HTTPS_SOURCE = re.compile(r"(?:^|[\s;])https:")


def test_nginx_conf_has_nosniff_frame_ancestors_and_api_origin_placeholder() -> None:
    text = Path("frontend/nginx.conf").read_text(encoding="utf-8")
    assert "X-Content-Type-Options nosniff always" in text
    assert "X-Frame-Options DENY always" in text
    assert "Referrer-Policy no-referrer always" in text
    assert "frame-ancestors 'none'" in text
    assert "__API_ORIGIN__" in text

    policies = re.findall(r'Content-Security-Policy "([^"]+)"', text)
    assert policies
    for policy in policies:
        assert _CSP_HTTPS_SOURCE.search(policy) is None
        img_src = policy.split("img-src", 1)[1].split(";", 1)[0]
        connect_src = policy.split("connect-src", 1)[1].split(";", 1)[0]
        assert "__API_ORIGIN__" in img_src
        assert "__API_ORIGIN__" in connect_src
        assert "https:" not in img_src
        assert "https:" not in connect_src


def test_student_and_teacher_dockerfiles_replace_api_origin_placeholder() -> None:
    for rel in ("frontend/Dockerfile.student", "frontend/Dockerfile.teacher"):
        text = Path(rel).read_text(encoding="utf-8")
        assert "ARG VITE_API_URL=http://localhost:8000" in text
        assert "sed" in text
        assert "__API_ORIGIN__" in text
        assert 'new URL(process.env.VITE_API_URL).origin' in text
        assert "grep -F '__API_ORIGIN__'" in text
        assert "COPY --from=build /app/nginx.conf /etc/nginx/conf.d/default.conf" in text


def test_ci_and_ghcr_pass_vite_api_url_build_arg() -> None:
    ci = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    docker = Path(".github/workflows/docker.yml").read_text(encoding="utf-8")
    assert "VITE_API_URL=http://localhost:8000" in ci
    assert "VITE_API_URL=http://localhost:8000" in docker
