package authapi

import (
	"bytes"
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	domainauth "go-api/internal/domain/auth"

	"github.com/stretchr/testify/require"
)

type fakeUsecase struct {
	output StudentLoginOutput
	err    error
}

func (f fakeUsecase) StudentLogin(_ context.Context, _ StudentLoginInput) (StudentLoginOutput, error) {
	return f.output, f.err
}

func TestStudentLoginHandler_Success(t *testing.T) {
	h := NewHandler(fakeUsecase{
		output: StudentLoginOutput{AccessToken: "access-token"},
	})

	body := []byte(`{"student_id":"stu1","credential":"S-123"}`)
	req := httptest.NewRequest(http.MethodPost, "/api/v2/auth/student/login", bytes.NewReader(body))
	rr := httptest.NewRecorder()

	h.StudentLogin(rr, req)

	require.Equal(t, http.StatusOK, rr.Code)
	require.JSONEq(t, `{"access_token":"access-token"}`, rr.Body.String())
}

func TestStudentLoginHandler_InvalidCredential(t *testing.T) {
	h := NewHandler(fakeUsecase{
		err: domainauth.ErrAuthInvalidCredential,
	})

	body := []byte(`{"student_id":"stu1","credential":"wrong"}`)
	req := httptest.NewRequest(http.MethodPost, "/api/v2/auth/student/login", bytes.NewReader(body))
	rr := httptest.NewRecorder()

	h.StudentLogin(rr, req)

	require.Equal(t, http.StatusUnauthorized, rr.Code)
	require.JSONEq(t, `{"error_code":"AUTH_INVALID_CREDENTIAL","message":"invalid credential"}`, rr.Body.String())
}

func TestStudentLoginHandler_UnexpectedError(t *testing.T) {
	h := NewHandler(fakeUsecase{
		err: errors.New("db unavailable"),
	})

	body := []byte(`{"student_id":"stu1","credential":"S-123"}`)
	req := httptest.NewRequest(http.MethodPost, "/api/v2/auth/student/login", bytes.NewReader(body))
	rr := httptest.NewRecorder()

	h.StudentLogin(rr, req)

	require.Equal(t, http.StatusInternalServerError, rr.Code)
	require.JSONEq(t, `{"error_code":"AUTH_LOGIN_FAILED","message":"login failed"}`, rr.Body.String())
}
