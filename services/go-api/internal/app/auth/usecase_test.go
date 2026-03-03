package auth

import (
	"context"
	"errors"
	"testing"

	domainauth "go-api/internal/domain/auth"

	"github.com/stretchr/testify/require"
)

type fakeRepo struct {
	ok  bool
	err error
}

func (f fakeRepo) VerifyStudentCredential(_ context.Context, _ string, _ string) (bool, error) {
	return f.ok, f.err
}

type fakeIssuer struct {
	token string
	err   error
}

func (f fakeIssuer) IssueStudentToken(_ context.Context, _ string) (string, error) {
	return f.token, f.err
}

func TestStudentLogin_WithValidToken_ReturnsAccessToken(t *testing.T) {
	uc := NewUsecase(fakeRepo{ok: true}, fakeIssuer{token: "access-token"})

	out, err := uc.StudentLogin(context.Background(), StudentLoginInput{
		StudentID:  "stu1",
		Credential: "S-123",
	})

	require.NoError(t, err)
	require.Equal(t, "access-token", out.AccessToken)
}

func TestStudentLogin_WithInvalidCredential_ReturnsDomainError(t *testing.T) {
	uc := NewUsecase(fakeRepo{ok: false}, fakeIssuer{token: "unused"})

	_, err := uc.StudentLogin(context.Background(), StudentLoginInput{
		StudentID:  "stu1",
		Credential: "wrong",
	})

	require.ErrorIs(t, err, domainauth.ErrAuthInvalidCredential)
}

func TestStudentLogin_PropagatesRepositoryErrors(t *testing.T) {
	uc := NewUsecase(fakeRepo{err: errors.New("db down")}, fakeIssuer{token: "unused"})

	_, err := uc.StudentLogin(context.Background(), StudentLoginInput{
		StudentID:  "stu1",
		Credential: "S-123",
	})

	require.ErrorContains(t, err, "db down")
}
