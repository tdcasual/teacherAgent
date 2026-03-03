package files

import (
	"context"

	domainfiles "go-api/internal/domain/files"
)

type MetadataStorage interface {
	SaveMetadata(ctx context.Context, fileName string, sizeBytes int64) (string, error)
}

type UploadInput struct {
	FileName  string
	SizeBytes int64
}

type UploadOutput struct {
	ResourceID string
}

type Usecase struct {
	storage      MetadataStorage
	maxSizeBytes int64
}

func NewUsecase(storage MetadataStorage, maxSizeBytes int64) Usecase {
	if maxSizeBytes <= 0 {
		maxSizeBytes = 50 << 20
	}
	return Usecase{
		storage:      storage,
		maxSizeBytes: maxSizeBytes,
	}
}

func (u Usecase) Upload(ctx context.Context, in UploadInput) (UploadOutput, error) {
	if in.SizeBytes > u.maxSizeBytes {
		return UploadOutput{}, domainfiles.ErrFileTooLarge
	}

	resourceID, err := u.storage.SaveMetadata(ctx, in.FileName, in.SizeBytes)
	if err != nil {
		return UploadOutput{}, err
	}

	return UploadOutput{ResourceID: resourceID}, nil
}
