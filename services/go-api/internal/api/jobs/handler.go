package jobsapi

import (
	"context"
	"encoding/json"
	"net/http"

	httpapi "go-api/internal/platform/http"

	"github.com/go-chi/chi/v5"
)

type JobStateResolver interface {
	ResolveJobState(ctx context.Context, jobID string) (string, error)
}

type Handler struct {
	resolver JobStateResolver
}

type statusResponse struct {
	JobID string `json:"job_id"`
	State string `json:"state"`
}

func NewHandler(resolver JobStateResolver) Handler {
	return Handler{resolver: resolver}
}

func (h Handler) GetStatus(w http.ResponseWriter, r *http.Request) {
	jobID := chi.URLParam(r, "jobID")
	if jobID == "" {
		httpapi.WriteError(w, http.StatusBadRequest, "JOB_ID_REQUIRED", "job id is required")
		return
	}

	state, err := h.resolver.ResolveJobState(r.Context(), jobID)
	if err != nil {
		httpapi.WriteError(w, http.StatusInternalServerError, "JOB_STATUS_FAILED", "job status failed")
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(statusResponse{
		JobID: jobID,
		State: state,
	})
}
