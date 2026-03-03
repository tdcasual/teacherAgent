package adminapi

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"

	domainadmin "go-api/internal/domain/admin"
	httpapi "go-api/internal/platform/http"
)

type ResetTeacherTokenInput struct {
	TeacherID string
}

type ResetTeacherTokenOutput struct {
	Token string
}

type AdminUsecase interface {
	ResetTeacherToken(ctx context.Context, in ResetTeacherTokenInput) (ResetTeacherTokenOutput, error)
}

type resetTeacherTokenRequest struct {
	TeacherID string `json:"teacher_id"`
}

type resetTeacherTokenResponse struct {
	Token string `json:"token"`
}

type Handler struct {
	usecase AdminUsecase
}

func NewHandler(usecase AdminUsecase) Handler {
	return Handler{usecase: usecase}
}

func (h Handler) ResetTeacherToken(w http.ResponseWriter, r *http.Request) {
	var req resetTeacherTokenRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		httpapi.WriteError(w, http.StatusBadRequest, "ADMIN_INVALID_PAYLOAD", "invalid payload")
		return
	}

	out, err := h.usecase.ResetTeacherToken(r.Context(), ResetTeacherTokenInput{
		TeacherID: req.TeacherID,
	})
	if err != nil {
		if errors.Is(err, domainadmin.ErrAdminTeacherRequired) {
			httpapi.WriteError(w, http.StatusBadRequest, "ADMIN_TEACHER_REQUIRED", "teacher is required")
			return
		}
		httpapi.WriteError(w, http.StatusInternalServerError, "ADMIN_RESET_TOKEN_FAILED", "reset token failed")
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(resetTeacherTokenResponse{
		Token: out.Token,
	})
}
