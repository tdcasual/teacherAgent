package chatapi

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"

	domainchat "go-api/internal/domain/chat"
	httpapi "go-api/internal/platform/http"
)

type SendMessageInput struct {
	SessionID string
	Message   string
}

type SendMessageOutput struct {
	JobID string
}

type ChatUsecase interface {
	SendMessage(ctx context.Context, in SendMessageInput) (SendMessageOutput, error)
}

type sendMessageRequest struct {
	SessionID string `json:"session_id"`
	Message   string `json:"message"`
}

type sendMessageResponse struct {
	JobID  string `json:"job_id"`
	Status string `json:"status"`
}

type Handler struct {
	usecase ChatUsecase
}

func NewHandler(usecase ChatUsecase) Handler {
	return Handler{usecase: usecase}
}

func (h Handler) SendMessage(w http.ResponseWriter, r *http.Request) {
	var req sendMessageRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		httpapi.WriteError(w, http.StatusBadRequest, "CHAT_INVALID_PAYLOAD", "invalid payload")
		return
	}

	out, err := h.usecase.SendMessage(r.Context(), SendMessageInput{
		SessionID: req.SessionID,
		Message:   req.Message,
	})
	if err != nil {
		switch {
		case errors.Is(err, domainchat.ErrChatSessionRequired):
			httpapi.WriteError(w, http.StatusBadRequest, "CHAT_SESSION_REQUIRED", "session is required")
			return
		case errors.Is(err, domainchat.ErrChatMessageRequired):
			httpapi.WriteError(w, http.StatusBadRequest, "CHAT_MESSAGE_REQUIRED", "message is required")
			return
		default:
			httpapi.WriteError(w, http.StatusInternalServerError, "CHAT_SEND_FAILED", "send failed")
			return
		}
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(sendMessageResponse{
		JobID:  out.JobID,
		Status: "queued",
	})
}
