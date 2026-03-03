package assignmentapi

import (
	"bytes"
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	domainassignment "go-api/internal/domain/assignment"

	"github.com/stretchr/testify/require"
)

type fakeUsecase struct {
	output ConfirmDraftOutput
	err    error
}

func (f fakeUsecase) ConfirmDraft(_ context.Context, _ ConfirmDraftInput) (ConfirmDraftOutput, error) {
	return f.output, f.err
}

func TestConfirmDraftHandler_Success(t *testing.T) {
	h := NewHandler(fakeUsecase{
		output: ConfirmDraftOutput{Status: "queued"},
	})

	req := httptest.NewRequest(http.MethodPost, "/api/v2/assignment/confirm", bytes.NewReader([]byte(`{"draft_id":"d1"}`)))
	rr := httptest.NewRecorder()

	h.ConfirmDraft(rr, req)

	require.Equal(t, http.StatusOK, rr.Code)
	require.JSONEq(t, `{"status":"queued"}`, rr.Body.String())
}

func TestConfirmDraftHandler_InvalidState(t *testing.T) {
	h := NewHandler(fakeUsecase{
		err: domainassignment.ErrAssignmentInvalidState,
	})

	req := httptest.NewRequest(http.MethodPost, "/api/v2/assignment/confirm", bytes.NewReader([]byte(`{"draft_id":"d1"}`)))
	rr := httptest.NewRecorder()

	h.ConfirmDraft(rr, req)

	require.Equal(t, http.StatusConflict, rr.Code)
	require.JSONEq(t, `{"error_code":"ASSIGNMENT_INVALID_STATE","message":"invalid draft state"}`, rr.Body.String())
}

func TestConfirmDraftHandler_UnexpectedError(t *testing.T) {
	h := NewHandler(fakeUsecase{
		err: errors.New("db unavailable"),
	})

	req := httptest.NewRequest(http.MethodPost, "/api/v2/assignment/confirm", bytes.NewReader([]byte(`{"draft_id":"d1"}`)))
	rr := httptest.NewRecorder()

	h.ConfirmDraft(rr, req)

	require.Equal(t, http.StatusInternalServerError, rr.Code)
	require.JSONEq(t, `{"error_code":"ASSIGNMENT_CONFIRM_FAILED","message":"confirm failed"}`, rr.Body.String())
}
