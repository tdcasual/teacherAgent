package files

import (
	"context"
	"testing"

	domainfiles "go-api/internal/domain/files"

	"github.com/stretchr/testify/require"
)

type fakeStorage struct {
	resourceID string
	err        error
}

func (f fakeStorage) SaveMetadata(_ context.Context, _ string, _ int64) (string, error) {
	return f.resourceID, f.err
}

func TestUploadFile_RejectsOversize(t *testing.T) {
	uc := NewUsecase(fakeStorage{resourceID: "unused"}, 50<<20)

	_, err := uc.Upload(context.Background(), UploadInput{
		FileName:  "big.pdf",
		SizeBytes: 60 << 20,
	})

	require.ErrorIs(t, err, domainfiles.ErrFileTooLarge)
}

func TestUploadFile_Success(t *testing.T) {
	uc := NewUsecase(fakeStorage{resourceID: "res-1"}, 50<<20)

	out, err := uc.Upload(context.Background(), UploadInput{
		FileName:  "small.pdf",
		SizeBytes: 1024,
	})

	require.NoError(t, err)
	require.Equal(t, "res-1", out.ResourceID)
}
