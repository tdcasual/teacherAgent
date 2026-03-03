package main

import (
	"context"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	"go-api/internal/platform/config"
	applog "go-api/internal/platform/log"
	server "go-api/internal/platform/server"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		panic(err)
	}

	logger := applog.New()
	logger.Info(
		"starting go-api server",
		"addr", cfg.Addr,
		"embedding_model", cfg.Models.EmbeddingModelID,
		"drawing_model", cfg.Models.DrawingModelID,
		"image_generation_extension_enabled", cfg.Models.ImageGenerationModelID != "",
		"video_generation_extension_enabled", cfg.Models.VideoGenerationModelID != "",
	)

	httpServer := &http.Server{
		Addr:    cfg.Addr,
		Handler: server.NewRouter(),
	}

	shutdownDone := make(chan struct{})
	go func() {
		defer close(shutdownDone)
		sigCh := make(chan os.Signal, 1)
		signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
		<-sigCh
		_ = httpServer.Shutdown(context.Background())
	}()

	if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		logger.Error("server failed", "error", err)
		os.Exit(1)
	}

	<-shutdownDone
}
