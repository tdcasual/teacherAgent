package jobsapi

import (
	"bytes"
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/stretchr/testify/require"
)

type fakeResolver struct {
	state string
	err   error
}

func (f fakeResolver) ResolveJobState(_ context.Context, _ string) (string, error) {
	return f.state, f.err
}

func TestGetStatus_ReturnsState(t *testing.T) {
	h := NewHandler(fakeResolver{state: "done"})
	req := httptest.NewRequest(http.MethodGet, "/api/v2/jobs/job-1", bytes.NewReader(nil))
	rr := httptest.NewRecorder()

	rctx := chi.NewRouteContext()
	rctx.URLParams.Add("jobID", "job-1")
	req = req.WithContext(context.WithValue(req.Context(), chi.RouteCtxKey, rctx))

	h.GetStatus(rr, req)

	require.Equal(t, http.StatusOK, rr.Code)
	require.JSONEq(t, `{"job_id":"job-1","state":"done"}`, rr.Body.String())
}

func TestGetStatus_RequiresJobID(t *testing.T) {
	h := NewHandler(fakeResolver{state: "done"})
	req := httptest.NewRequest(http.MethodGet, "/api/v2/jobs/", bytes.NewReader(nil))
	rr := httptest.NewRecorder()

	rctx := chi.NewRouteContext()
	req = req.WithContext(context.WithValue(req.Context(), chi.RouteCtxKey, rctx))

	h.GetStatus(rr, req)

	require.Equal(t, http.StatusBadRequest, rr.Code)
	require.JSONEq(t, `{"error_code":"JOB_ID_REQUIRED","message":"job id is required"}`, rr.Body.String())
}

func TestGetStatus_PropagatesResolverError(t *testing.T) {
	h := NewHandler(fakeResolver{err: errors.New("store down")})
	req := httptest.NewRequest(http.MethodGet, "/api/v2/jobs/job-1", bytes.NewReader(nil))
	rr := httptest.NewRecorder()

	rctx := chi.NewRouteContext()
	rctx.URLParams.Add("jobID", "job-1")
	req = req.WithContext(context.WithValue(req.Context(), chi.RouteCtxKey, rctx))

	h.GetStatus(rr, req)

	require.Equal(t, http.StatusInternalServerError, rr.Code)
	require.JSONEq(t, `{"error_code":"JOB_STATUS_FAILED","message":"job status failed"}`, rr.Body.String())
}
