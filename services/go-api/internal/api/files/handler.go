package filesapi

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"

	domainfiles "go-api/internal/domain/files"
	httpapi "go-api/internal/platform/http"
)

type UploadInput struct {
	FileName  string
	SizeBytes int64
}

type UploadOutput struct {
	ResourceID string
}

type UploadUsecase interface {
	Upload(ctx context.Context, in UploadInput) (UploadOutput, error)
}

type uploadRequest struct {
	FileName  string `json:"file_name"`
	SizeBytes int64  `json:"size_bytes"`
}

type uploadResponse struct {
	ResourceID string `json:"resource_id"`
}

type Handler struct {
	usecase UploadUsecase
}

func NewHandler(usecase UploadUsecase) Handler {
	return Handler{usecase: usecase}
}

func (h Handler) Upload(w http.ResponseWriter, r *http.Request) {
	var req uploadRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		httpapi.WriteError(w, http.StatusBadRequest, "FILE_INVALID_PAYLOAD", "invalid payload")
		return
	}

	out, err := h.usecase.Upload(r.Context(), UploadInput{
		FileName:  req.FileName,
		SizeBytes: req.SizeBytes,
	})
	if err != nil {
		if errors.Is(err, domainfiles.ErrFileTooLarge) {
			httpapi.WriteError(w, http.StatusRequestEntityTooLarge, "FILE_TOO_LARGE", "file too large")
			return
		}
		httpapi.WriteError(w, http.StatusInternalServerError, "FILE_UPLOAD_FAILED", "upload failed")
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(uploadResponse{
		ResourceID: out.ResourceID,
	})
}
