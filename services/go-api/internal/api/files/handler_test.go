package filesapi

import (
	"bytes"
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	domainfiles "go-api/internal/domain/files"

	"github.com/stretchr/testify/require"
)

type fakeUsecase struct {
	output UploadOutput
	err    error
}

func (f fakeUsecase) Upload(_ context.Context, _ UploadInput) (UploadOutput, error) {
	return f.output, f.err
}

func TestUploadHandler_Success(t *testing.T) {
	h := NewHandler(fakeUsecase{
		output: UploadOutput{ResourceID: "res-1"},
	})

	reqBody := []byte(`{"file_name":"small.pdf","size_bytes":1024}`)
	req := httptest.NewRequest(http.MethodPost, "/api/v2/files/upload", bytes.NewReader(reqBody))
	rr := httptest.NewRecorder()

	h.Upload(rr, req)

	require.Equal(t, http.StatusOK, rr.Code)
	require.JSONEq(t, `{"resource_id":"res-1"}`, rr.Body.String())
}

func TestUploadHandler_FileTooLarge(t *testing.T) {
	h := NewHandler(fakeUsecase{
		err: domainfiles.ErrFileTooLarge,
	})

	reqBody := []byte(`{"file_name":"big.pdf","size_bytes":70000000}`)
	req := httptest.NewRequest(http.MethodPost, "/api/v2/files/upload", bytes.NewReader(reqBody))
	rr := httptest.NewRecorder()

	h.Upload(rr, req)

	require.Equal(t, http.StatusRequestEntityTooLarge, rr.Code)
	require.JSONEq(t, `{"error_code":"FILE_TOO_LARGE","message":"file too large"}`, rr.Body.String())
}

func TestUploadHandler_UnexpectedError(t *testing.T) {
	h := NewHandler(fakeUsecase{
		err: errors.New("storage error"),
	})

	reqBody := []byte(`{"file_name":"small.pdf","size_bytes":1024}`)
	req := httptest.NewRequest(http.MethodPost, "/api/v2/files/upload", bytes.NewReader(reqBody))
	rr := httptest.NewRecorder()

	h.Upload(rr, req)

	require.Equal(t, http.StatusInternalServerError, rr.Code)
	require.JSONEq(t, `{"error_code":"FILE_UPLOAD_FAILED","message":"upload failed"}`, rr.Body.String())
}
