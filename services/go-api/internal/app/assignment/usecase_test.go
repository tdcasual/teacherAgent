package assignment

import (
	"context"
	"errors"
	"testing"

	domainassignment "go-api/internal/domain/assignment"

	"github.com/stretchr/testify/require"
)

type fakeRepo struct {
	status    domainassignment.DraftStatus
	getErr    error
	updateErr error
	updated   domainassignment.DraftStatus
}

func (f *fakeRepo) GetDraftStatus(_ context.Context, _ string) (domainassignment.DraftStatus, error) {
	return f.status, f.getErr
}

func (f *fakeRepo) UpdateDraftStatus(_ context.Context, _ string, status domainassignment.DraftStatus) error {
	f.updated = status
	return f.updateErr
}

func TestConfirmDraft_TransitionsToQueued(t *testing.T) {
	repo := &fakeRepo{status: domainassignment.DraftStatusSaved}
	uc := NewUsecase(repo)

	out, err := uc.ConfirmDraft(context.Background(), ConfirmDraftInput{DraftID: "d1"})

	require.NoError(t, err)
	require.Equal(t, "queued", out.Status)
	require.Equal(t, domainassignment.DraftStatusQueued, repo.updated)
}

func TestConfirmDraft_InvalidState(t *testing.T) {
	repo := &fakeRepo{status: domainassignment.DraftStatusQueued}
	uc := NewUsecase(repo)

	_, err := uc.ConfirmDraft(context.Background(), ConfirmDraftInput{DraftID: "d1"})

	require.ErrorIs(t, err, domainassignment.ErrAssignmentInvalidState)
}

func TestConfirmDraft_PropagatesRepoErrors(t *testing.T) {
	repo := &fakeRepo{getErr: errors.New("db unavailable")}
	uc := NewUsecase(repo)

	_, err := uc.ConfirmDraft(context.Background(), ConfirmDraftInput{DraftID: "d1"})

	require.ErrorContains(t, err, "db unavailable")
}
