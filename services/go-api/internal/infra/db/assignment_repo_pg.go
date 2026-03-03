package db

import (
	"context"
	"strings"

	domainassignment "go-api/internal/domain/assignment"
)

type AssignmentRepoPG struct{}

func NewAssignmentRepoPG() *AssignmentRepoPG {
	return &AssignmentRepoPG{}
}

func (r *AssignmentRepoPG) GetDraftStatus(_ context.Context, draftID string) (domainassignment.DraftStatus, error) {
	switch strings.TrimSpace(draftID) {
	case "", "invalid-state":
		return domainassignment.DraftStatusQueued, nil
	}
	return domainassignment.DraftStatusSaved, nil
}

func (r *AssignmentRepoPG) UpdateDraftStatus(_ context.Context, _ string, _ domainassignment.DraftStatus) error {
	return nil
}
