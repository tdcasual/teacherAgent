package examapi

import (
	"bytes"
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	domainexam "go-api/internal/domain/exam"

	"github.com/stretchr/testify/require"
)

type fakeUsecase struct {
	output CreateExamParseJobOutput
	err    error
}

func (f fakeUsecase) CreateExamParseJob(_ context.Context, _ CreateExamParseJobInput) (CreateExamParseJobOutput, error) {
	return f.output, f.err
}

func TestCreateExamParseJobHandler_Success(t *testing.T) {
	h := NewHandler(fakeUsecase{
		output: CreateExamParseJobOutput{JobID: "job-1"},
	})

	req := httptest.NewRequest(http.MethodPost, "/api/v2/exam/parse", bytes.NewReader([]byte(`{"resource_id":"res-1"}`)))
	rr := httptest.NewRecorder()

	h.CreateExamParseJob(rr, req)

	require.Equal(t, http.StatusOK, rr.Code)
	require.JSONEq(t, `{"job_id":"job-1","status":"queued"}`, rr.Body.String())
}

func TestCreateExamParseJobHandler_MissingResource(t *testing.T) {
	h := NewHandler(fakeUsecase{
		err: domainexam.ErrExamResourceRequired,
	})

	req := httptest.NewRequest(http.MethodPost, "/api/v2/exam/parse", bytes.NewReader([]byte(`{"resource_id":""}`)))
	rr := httptest.NewRecorder()

	h.CreateExamParseJob(rr, req)

	require.Equal(t, http.StatusBadRequest, rr.Code)
	require.JSONEq(t, `{"error_code":"EXAM_RESOURCE_REQUIRED","message":"resource is required"}`, rr.Body.String())
}

func TestCreateExamParseJobHandler_UnexpectedError(t *testing.T) {
	h := NewHandler(fakeUsecase{
		err: errors.New("queue unavailable"),
	})

	req := httptest.NewRequest(http.MethodPost, "/api/v2/exam/parse", bytes.NewReader([]byte(`{"resource_id":"res-1"}`)))
	rr := httptest.NewRecorder()

	h.CreateExamParseJob(rr, req)

	require.Equal(t, http.StatusInternalServerError, rr.Code)
	require.JSONEq(t, `{"error_code":"EXAM_JOB_CREATE_FAILED","message":"create exam job failed"}`, rr.Body.String())
}
