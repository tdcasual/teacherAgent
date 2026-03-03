package chatapi

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"

	domainchat "go-api/internal/domain/chat"

	"github.com/stretchr/testify/require"
)

type fakeUsecase struct {
	events <-chan domainchat.JobEvent
	err    error
}

func (f fakeUsecase) StreamJobEvents(_ context.Context, _ string) (<-chan domainchat.JobEvent, error) {
	return f.events, f.err
}

func TestStreamJobEvents_WritesSSEFrames(t *testing.T) {
	events := make(chan domainchat.JobEvent, 2)
	events <- domainchat.JobEvent{Event: "progress", Data: "50%"}
	events <- domainchat.JobEvent{Event: "done", Data: "ok"}
	close(events)

	h := NewSSEHandler(fakeUsecase{events: events})
	req := httptest.NewRequest(http.MethodGet, "/api/v2/chat/events?job_id=job-1", nil)
	rr := httptest.NewRecorder()

	h.StreamJobEvents(rr, req)

	require.Equal(t, http.StatusOK, rr.Code)
	require.Contains(t, rr.Body.String(), "event: progress")
	require.Contains(t, rr.Body.String(), "data: 50%")
	require.Contains(t, rr.Body.String(), "event: done")
}
