package examapi

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"

	domainexam "go-api/internal/domain/exam"
	httpapi "go-api/internal/platform/http"
)

type CreateExamParseJobInput struct {
	ResourceID string
}

type CreateExamParseJobOutput struct {
	JobID string
}

type ExamUsecase interface {
	CreateExamParseJob(ctx context.Context, in CreateExamParseJobInput) (CreateExamParseJobOutput, error)
}

type createExamParseRequest struct {
	ResourceID string `json:"resource_id"`
}

type createExamParseResponse struct {
	JobID  string `json:"job_id"`
	Status string `json:"status"`
}

type Handler struct {
	usecase ExamUsecase
}

func NewHandler(usecase ExamUsecase) Handler {
	return Handler{usecase: usecase}
}

func (h Handler) CreateExamParseJob(w http.ResponseWriter, r *http.Request) {
	var req createExamParseRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		httpapi.WriteError(w, http.StatusBadRequest, "EXAM_INVALID_PAYLOAD", "invalid payload")
		return
	}

	out, err := h.usecase.CreateExamParseJob(r.Context(), CreateExamParseJobInput{
		ResourceID: req.ResourceID,
	})
	if err != nil {
		if errors.Is(err, domainexam.ErrExamResourceRequired) {
			httpapi.WriteError(w, http.StatusBadRequest, "EXAM_RESOURCE_REQUIRED", "resource is required")
			return
		}
		httpapi.WriteError(w, http.StatusInternalServerError, "EXAM_JOB_CREATE_FAILED", "create exam job failed")
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(createExamParseResponse{
		JobID:  out.JobID,
		Status: "queued",
	})
}
