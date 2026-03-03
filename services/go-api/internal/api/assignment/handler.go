package assignmentapi

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"

	domainassignment "go-api/internal/domain/assignment"
	httpapi "go-api/internal/platform/http"
)

type ConfirmDraftInput struct {
	DraftID string
}

type ConfirmDraftOutput struct {
	Status string
}

type ConfirmUsecase interface {
	ConfirmDraft(ctx context.Context, in ConfirmDraftInput) (ConfirmDraftOutput, error)
}

type confirmDraftRequest struct {
	DraftID string `json:"draft_id"`
}

type confirmDraftResponse struct {
	Status string `json:"status"`
}

type Handler struct {
	usecase ConfirmUsecase
}

func NewHandler(usecase ConfirmUsecase) Handler {
	return Handler{usecase: usecase}
}

func (h Handler) ConfirmDraft(w http.ResponseWriter, r *http.Request) {
	var req confirmDraftRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		httpapi.WriteError(w, http.StatusBadRequest, "ASSIGNMENT_INVALID_PAYLOAD", "invalid payload")
		return
	}

	out, err := h.usecase.ConfirmDraft(r.Context(), ConfirmDraftInput{
		DraftID: req.DraftID,
	})
	if err != nil {
		if errors.Is(err, domainassignment.ErrAssignmentInvalidState) {
			httpapi.WriteError(w, http.StatusConflict, "ASSIGNMENT_INVALID_STATE", "invalid draft state")
			return
		}
		httpapi.WriteError(w, http.StatusInternalServerError, "ASSIGNMENT_CONFIRM_FAILED", "confirm failed")
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(confirmDraftResponse{
		Status: out.Status,
	})
}
