package server

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/require"
)

func requestJSON(router http.Handler, method, path, body string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rr := httptest.NewRecorder()
	router.ServeHTTP(rr, req)
	return rr
}

func requestRaw(router http.Handler, method, path string, body []byte) *httptest.ResponseRecorder {
	req := httptest.NewRequest(method, path, bytes.NewReader(body))
	rr := httptest.NewRecorder()
	router.ServeHTTP(rr, req)
	return rr
}

func TestRouter_HealthAlias(t *testing.T) {
	router := NewRouter()
	rr := requestRaw(router, http.MethodGet, "/health", nil)
	require.Equal(t, http.StatusOK, rr.Code)
	require.JSONEq(t, `{"status":"ok"}`, rr.Body.String())
}

func TestRouter_StudentLoginSuccess(t *testing.T) {
	router := NewRouter()
	rr := requestJSON(router, http.MethodPost, "/api/v2/auth/student/login", `{"student_id":"stu-1","credential":"S-123"}`)
	require.Equal(t, http.StatusOK, rr.Code)
	require.JSONEq(t, `{"access_token":"token-stu-1"}`, rr.Body.String())
}

func TestRouter_StudentLoginInvalidCredential(t *testing.T) {
	router := NewRouter()
	rr := requestJSON(router, http.MethodPost, "/api/v2/auth/student/login", `{"student_id":"stu-1","credential":"bad"}`)
	require.Equal(t, http.StatusUnauthorized, rr.Code)
	require.JSONEq(t, `{"error_code":"AUTH_INVALID_CREDENTIAL","message":"invalid credential"}`, rr.Body.String())
}

func TestRouter_FileUploadGuardrail(t *testing.T) {
	router := NewRouter()
	rr := requestJSON(router, http.MethodPost, "/api/v2/files/upload", `{"file_name":"big.pdf","size_bytes":73400320}`)
	require.Equal(t, http.StatusRequestEntityTooLarge, rr.Code)
	require.JSONEq(t, `{"error_code":"FILE_TOO_LARGE","message":"file too large"}`, rr.Body.String())
}

func TestRouter_AssignmentConfirmInvalidState(t *testing.T) {
	router := NewRouter()
	rr := requestJSON(router, http.MethodPost, "/api/v2/assignment/confirm", `{"draft_id":"invalid-state"}`)
	require.Equal(t, http.StatusConflict, rr.Code)
	require.JSONEq(t, `{"error_code":"ASSIGNMENT_INVALID_STATE","message":"invalid draft state"}`, rr.Body.String())
}

func TestRouter_ExamParseValidation(t *testing.T) {
	router := NewRouter()
	rr := requestJSON(router, http.MethodPost, "/api/v2/exam/parse", `{"resource_id":""}`)
	require.Equal(t, http.StatusBadRequest, rr.Code)
	require.JSONEq(t, `{"error_code":"EXAM_RESOURCE_REQUIRED","message":"resource is required"}`, rr.Body.String())
}

func TestRouter_ChatSendValidation(t *testing.T) {
	router := NewRouter()
	rr := requestJSON(router, http.MethodPost, "/api/v2/chat/send", `{"session_id":"s1","message":""}`)
	require.Equal(t, http.StatusBadRequest, rr.Code)
	require.JSONEq(t, `{"error_code":"CHAT_MESSAGE_REQUIRED","message":"message is required"}`, rr.Body.String())
}

func TestRouter_ChatEventsAndJobStatus(t *testing.T) {
	router := NewRouter()

	stream := requestRaw(router, http.MethodGet, "/api/v2/chat/events?job_id=chat-job-1", nil)
	require.Equal(t, http.StatusOK, stream.Code)
	require.Contains(t, stream.Body.String(), "event: done")

	status := requestRaw(router, http.MethodGet, "/api/v2/jobs/chat-job-1", nil)
	require.Equal(t, http.StatusOK, status.Code)
	require.JSONEq(t, `{"job_id":"chat-job-1","state":"done"}`, status.Body.String())
}

func TestRouter_AdminResetTokenFailurePath(t *testing.T) {
	router := NewRouter()
	rr := requestJSON(router, http.MethodPost, "/api/v2/admin/teacher/reset-token", `{"teacher_id":"fail"}`)
	require.Equal(t, http.StatusInternalServerError, rr.Code)
	require.JSONEq(t, `{"error_code":"ADMIN_RESET_TOKEN_FAILED","message":"reset token failed"}`, rr.Body.String())
}

func TestRouter_ChartImageFile(t *testing.T) {
	uploadsDir := t.TempDir()
	chartDir := filepath.Join(uploadsDir, "charts", "run-1")
	require.NoError(t, os.MkdirAll(chartDir, 0o755))
	require.NoError(t, os.WriteFile(filepath.Join(chartDir, "plot.png"), []byte("PNGDATA"), 0o644))

	t.Setenv("GO_API_UPLOADS_DIR", uploadsDir)
	router := NewRouter()

	rr := requestRaw(router, http.MethodGet, "/charts/run-1/plot.png", nil)
	require.Equal(t, http.StatusOK, rr.Code)
	require.Equal(t, "PNGDATA", rr.Body.String())
}

func TestRouter_ChartRunMeta(t *testing.T) {
	uploadsDir := t.TempDir()
	metaDir := filepath.Join(uploadsDir, "chart-runs", "run-2")
	require.NoError(t, os.MkdirAll(metaDir, 0o755))
	require.NoError(t, os.WriteFile(filepath.Join(metaDir, "meta.json"), []byte(`{"ok":true,"points":3}`), 0o644))

	t.Setenv("GO_API_UPLOADS_DIR", uploadsDir)
	router := NewRouter()

	rr := requestRaw(router, http.MethodGet, "/chart-runs/run-2/meta", nil)
	require.Equal(t, http.StatusOK, rr.Code)

	var out map[string]any
	require.NoError(t, json.Unmarshal(rr.Body.Bytes(), &out))
	require.Equal(t, true, out["ok"])
	require.EqualValues(t, 3, out["points"])
}
