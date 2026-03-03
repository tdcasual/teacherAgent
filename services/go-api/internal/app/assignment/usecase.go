package assignment

import (
	"context"

	domainassignment "go-api/internal/domain/assignment"
)

type DraftRepository interface {
	GetDraftStatus(ctx context.Context, draftID string) (domainassignment.DraftStatus, error)
	UpdateDraftStatus(ctx context.Context, draftID string, status domainassignment.DraftStatus) error
}

type ConfirmDraftInput struct {
	DraftID string
}

type ConfirmDraftOutput struct {
	Status string
}

type Usecase struct {
	repo DraftRepository
}

func NewUsecase(repo DraftRepository) Usecase {
	return Usecase{repo: repo}
}

func (u Usecase) ConfirmDraft(ctx context.Context, in ConfirmDraftInput) (ConfirmDraftOutput, error) {
	status, err := u.repo.GetDraftStatus(ctx, in.DraftID)
	if err != nil {
		return ConfirmDraftOutput{}, err
	}
	if status != domainassignment.DraftStatusSaved {
		return ConfirmDraftOutput{}, domainassignment.ErrAssignmentInvalidState
	}
	if err := u.repo.UpdateDraftStatus(ctx, in.DraftID, domainassignment.DraftStatusQueued); err != nil {
		return ConfirmDraftOutput{}, err
	}

	return ConfirmDraftOutput{Status: string(domainassignment.DraftStatusQueued)}, nil
}
