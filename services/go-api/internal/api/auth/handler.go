package authapi

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"

	domainauth "go-api/internal/domain/auth"
	httpapi "go-api/internal/platform/http"
)

type StudentLoginInput struct {
	StudentID  string
	Credential string
}

type StudentLoginOutput struct {
	AccessToken string
}

type LoginUsecase interface {
	StudentLogin(ctx context.Context, in StudentLoginInput) (StudentLoginOutput, error)
}

type studentLoginRequest struct {
	StudentID  string `json:"student_id"`
	Credential string `json:"credential"`
}

type studentLoginResponse struct {
	AccessToken string `json:"access_token"`
}

type Handler struct {
	usecase LoginUsecase
}

func NewHandler(usecase LoginUsecase) Handler {
	return Handler{usecase: usecase}
}

func (h Handler) StudentLogin(w http.ResponseWriter, r *http.Request) {
	var req studentLoginRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		httpapi.WriteError(w, http.StatusBadRequest, "AUTH_INVALID_PAYLOAD", "invalid payload")
		return
	}

	out, err := h.usecase.StudentLogin(r.Context(), StudentLoginInput{
		StudentID:  req.StudentID,
		Credential: req.Credential,
	})
	if err != nil {
		if errors.Is(err, domainauth.ErrAuthInvalidCredential) {
			httpapi.WriteError(w, http.StatusUnauthorized, "AUTH_INVALID_CREDENTIAL", "invalid credential")
			return
		}
		httpapi.WriteError(w, http.StatusInternalServerError, "AUTH_LOGIN_FAILED", "login failed")
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(studentLoginResponse{
		AccessToken: out.AccessToken,
	})
}
