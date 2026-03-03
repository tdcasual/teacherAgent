package adminapi

import (
	"bytes"
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	domainadmin "go-api/internal/domain/admin"

	"github.com/stretchr/testify/require"
)

type fakeUsecase struct {
	output ResetTeacherTokenOutput
	err    error
}

func (f fakeUsecase) ResetTeacherToken(_ context.Context, _ ResetTeacherTokenInput) (ResetTeacherTokenOutput, error) {
	return f.output, f.err
}

func TestResetTeacherTokenHandler_Success(t *testing.T) {
	h := NewHandler(fakeUsecase{
		output: ResetTeacherTokenOutput{Token: "T-NEW-1"},
	})

	req := httptest.NewRequest(http.MethodPost, "/api/v2/admin/teacher/reset-token", bytes.NewReader([]byte(`{"teacher_id":"t1"}`)))
	rr := httptest.NewRecorder()

	h.ResetTeacherToken(rr, req)

	require.Equal(t, http.StatusOK, rr.Code)
	require.JSONEq(t, `{"token":"T-NEW-1"}`, rr.Body.String())
}

func TestResetTeacherTokenHandler_RequiresTeacherID(t *testing.T) {
	h := NewHandler(fakeUsecase{
		err: domainadmin.ErrAdminTeacherRequired,
	})

	req := httptest.NewRequest(http.MethodPost, "/api/v2/admin/teacher/reset-token", bytes.NewReader([]byte(`{"teacher_id":""}`)))
	rr := httptest.NewRecorder()

	h.ResetTeacherToken(rr, req)

	require.Equal(t, http.StatusBadRequest, rr.Code)
	require.JSONEq(t, `{"error_code":"ADMIN_TEACHER_REQUIRED","message":"teacher is required"}`, rr.Body.String())
}

func TestResetTeacherTokenHandler_UnexpectedError(t *testing.T) {
	h := NewHandler(fakeUsecase{
		err: errors.New("db down"),
	})

	req := httptest.NewRequest(http.MethodPost, "/api/v2/admin/teacher/reset-token", bytes.NewReader([]byte(`{"teacher_id":"t1"}`)))
	rr := httptest.NewRecorder()

	h.ResetTeacherToken(rr, req)

	require.Equal(t, http.StatusInternalServerError, rr.Code)
	require.JSONEq(t, `{"error_code":"ADMIN_RESET_TOKEN_FAILED","message":"reset token failed"}`, rr.Body.String())
}
