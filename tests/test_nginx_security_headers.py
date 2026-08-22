from pathlib import Path


def test_nginx_conf_has_nosniff_frame_ancestors_and_api_origin_placeholder() -> None:
    text = Path("frontend/nginx.conf").read_text(encoding="utf-8")
    assert "X-Content-Type-Options nosniff" in text
    assert "frame-ancestors 'none'" in text
    assert "__API_ORIGIN__" in text
    assert "connect-src 'self' __API_ORIGIN__" in text
    assert "connect-src 'self' https:" not in text


def test_student_and_teacher_dockerfiles_replace_api_origin_placeholder() -> None:
    for rel in ("frontend/Dockerfile.student", "frontend/Dockerfile.teacher"):
        text = Path(rel).read_text(encoding="utf-8")
        assert "sed" in text
        assert "__API_ORIGIN__" in text
        assert 'new URL(process.env.VITE_API_URL).origin' in text
        assert "test -n \"$VITE_API_URL\"" in text
        assert "COPY --from=build /app/nginx.conf /etc/nginx/conf.d/default.conf" in text
