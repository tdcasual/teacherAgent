package admin

import (
	"context"

	domainadmin "go-api/internal/domain/admin"
)

type TeacherRepository interface {
	UpdateTeacherToken(ctx context.Context, teacherID, token string) error
}

type TokenGenerator interface {
	NewToken() string
}

type ResetTeacherTokenInput struct {
	TeacherID string
}

type ResetTeacherTokenOutput struct {
	Token string
}

type Usecase struct {
	repo      TeacherRepository
	generator TokenGenerator
}

func NewUsecase(repo TeacherRepository, generator TokenGenerator) Usecase {
	return Usecase{
		repo:      repo,
		generator: generator,
	}
}

func (u Usecase) ResetTeacherToken(ctx context.Context, in ResetTeacherTokenInput) (ResetTeacherTokenOutput, error) {
	if in.TeacherID == "" {
		return ResetTeacherTokenOutput{}, domainadmin.ErrAdminTeacherRequired
	}

	token := u.generator.NewToken()
	if err := u.repo.UpdateTeacherToken(ctx, in.TeacherID, token); err != nil {
		return ResetTeacherTokenOutput{}, err
	}

	return ResetTeacherTokenOutput{Token: token}, nil
}
