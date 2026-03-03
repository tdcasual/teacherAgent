package chatapi

import (
	"context"
	"fmt"
	"net/http"

	domainchat "go-api/internal/domain/chat"
	httpapi "go-api/internal/platform/http"
)

type SSEUsecase interface {
	StreamJobEvents(ctx context.Context, jobID string) (<-chan domainchat.JobEvent, error)
}

type SSEHandler struct {
	usecase SSEUsecase
}

func NewSSEHandler(usecase SSEUsecase) SSEHandler {
	return SSEHandler{usecase: usecase}
}

func (h SSEHandler) StreamJobEvents(w http.ResponseWriter, r *http.Request) {
	jobID := r.URL.Query().Get("job_id")
	events, err := h.usecase.StreamJobEvents(r.Context(), jobID)
	if err != nil {
		httpapi.WriteError(w, http.StatusBadRequest, "CHAT_INVALID_JOB", "invalid job id")
		return
	}

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.WriteHeader(http.StatusOK)

	flusher, ok := w.(http.Flusher)
	if !ok {
		httpapi.WriteError(w, http.StatusInternalServerError, "CHAT_STREAM_UNAVAILABLE", "stream unavailable")
		return
	}

	for event := range events {
		fmt.Fprintf(w, "event: %s\n", event.Event)
		fmt.Fprintf(w, "data: %s\n\n", event.Data)
		flusher.Flush()
	}
}
