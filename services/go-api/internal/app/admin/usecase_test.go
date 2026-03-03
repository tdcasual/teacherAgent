package admin

import (
	"context"
	"errors"
	"testing"

	domainadmin "go-api/internal/domain/admin"

	"github.com/stretchr/testify/require"
)

type fakeRepo struct {
	updatedTeacherID string
	updatedToken     string
	err              error
}

func (f *fakeRepo) UpdateTeacherToken(_ context.Context, teacherID, token string) error {
	f.updatedTeacherID = teacherID
	f.updatedToken = token
	return f.err
}

type fakeGenerator struct {
	token string
}

func (f fakeGenerator) NewToken() string {
	return f.token
}

func TestResetTeacherToken_ReturnsNewToken(t *testing.T) {
	repo := &fakeRepo{}
	uc := NewUsecase(repo, fakeGenerator{token: "T-NEW-1"})

	out, err := uc.ResetTeacherToken(context.Background(), ResetTeacherTokenInput{TeacherID: "t1"})

	require.NoError(t, err)
	require.Equal(t, "T-NEW-1", out.Token)
	require.Equal(t, "t1", repo.updatedTeacherID)
	require.Equal(t, "T-NEW-1", repo.updatedToken)
}

func TestResetTeacherToken_RequiresTeacherID(t *testing.T) {
	repo := &fakeRepo{}
	uc := NewUsecase(repo, fakeGenerator{token: "unused"})

	_, err := uc.ResetTeacherToken(context.Background(), ResetTeacherTokenInput{})

	require.ErrorIs(t, err, domainadmin.ErrAdminTeacherRequired)
}

func TestResetTeacherToken_PropagatesRepoError(t *testing.T) {
	repo := &fakeRepo{err: errors.New("db down")}
	uc := NewUsecase(repo, fakeGenerator{token: "T-NEW-1"})

	_, err := uc.ResetTeacherToken(context.Background(), ResetTeacherTokenInput{TeacherID: "t1"})

	require.ErrorContains(t, err, "db down")
}
