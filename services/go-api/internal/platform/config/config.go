package config

import (
	"errors"
	"os"
	"strings"
)

var ErrMissingDatabaseURL = errors.New("DATABASE_URL is required")

type Config struct {
	Addr        string
	DatabaseURL string
	Models      ModelPolicy
}

type ModelPolicy struct {
	EmbeddingModelID       string
	DrawingModelID         string
	ImageGenerationModelID string
	VideoGenerationModelID string
}

func Load() (Config, error) {
	databaseURL := strings.TrimSpace(os.Getenv("DATABASE_URL"))
	if databaseURL == "" {
		return Config{}, ErrMissingDatabaseURL
	}

	addr := strings.TrimSpace(os.Getenv("GO_API_ADDR"))
	if addr == "" {
		addr = ":8080"
	}

	embeddingModelID := getenvOrDefault("EMBEDDING_MODEL_ID", "text-embedding-3-large")
	drawingModelID := getenvOrDefault("DRAWING_MODEL_ID", "gpt-image-1")
	imageGenerationModelID := strings.TrimSpace(os.Getenv("IMAGE_GENERATION_MODEL_ID"))
	videoGenerationModelID := strings.TrimSpace(os.Getenv("VIDEO_GENERATION_MODEL_ID"))

	return Config{
		Addr:        addr,
		DatabaseURL: databaseURL,
		Models: ModelPolicy{
			EmbeddingModelID:       embeddingModelID,
			DrawingModelID:         drawingModelID,
			ImageGenerationModelID: imageGenerationModelID,
			VideoGenerationModelID: videoGenerationModelID,
		},
	}, nil
}

func getenvOrDefault(key, fallback string) string {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	return value
}
