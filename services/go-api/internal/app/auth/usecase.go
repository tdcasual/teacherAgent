package auth

import (
	"context"

	domainauth "go-api/internal/domain/auth"
)

type TokenIssuer interface {
	IssueStudentToken(ctx context.Context, studentID string) (string, error)
}

type StudentLoginInput struct {
	StudentID  string
	Credential string
}

type StudentLoginOutput struct {
	AccessToken string
}

type Usecase struct {
	repo   domainauth.StudentCredentialRepository
	issuer TokenIssuer
}

func NewUsecase(repo domainauth.StudentCredentialRepository, issuer TokenIssuer) Usecase {
	return Usecase{
		repo:   repo,
		issuer: issuer,
	}
}

func (u Usecase) StudentLogin(ctx context.Context, in StudentLoginInput) (StudentLoginOutput, error) {
	ok, err := u.repo.VerifyStudentCredential(ctx, in.StudentID, in.Credential)
	if err != nil {
		return StudentLoginOutput{}, err
	}
	if !ok {
		return StudentLoginOutput{}, domainauth.ErrAuthInvalidCredential
	}

	token, err := u.issuer.IssueStudentToken(ctx, in.StudentID)
	if err != nil {
		return StudentLoginOutput{}, err
	}

	return StudentLoginOutput{AccessToken: token}, nil
}
