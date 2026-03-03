package chartsapi

import (
	"encoding/json"
	"errors"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	httpapi "go-api/internal/platform/http"

	"github.com/go-chi/chi/v5"
)

type Handler struct {
	uploadsDir string
}

func NewHandler(uploadsDir string) Handler {
	dir := strings.TrimSpace(uploadsDir)
	if dir == "" {
		dir = "uploads"
	}
	return Handler{uploadsDir: dir}
}

func isSafeSegment(value string) bool {
	if value == "" {
		return false
	}
	if strings.Contains(value, "..") {
		return false
	}
	return !strings.ContainsAny(value, `/\`)
}

func (h Handler) ChartImageFile(w http.ResponseWriter, r *http.Request) {
	runID := chi.URLParam(r, "runID")
	fileName := chi.URLParam(r, "fileName")
	if !isSafeSegment(runID) || !isSafeSegment(fileName) {
		httpapi.WriteError(w, http.StatusBadRequest, "CHART_INVALID_PATH", "invalid chart path")
		return
	}

	path := filepath.Join(h.uploadsDir, "charts", runID, fileName)
	if _, err := os.Stat(path); err != nil {
		if errors.Is(err, os.ErrNotExist) {
			httpapi.WriteError(w, http.StatusNotFound, "CHART_NOT_FOUND", "chart file not found")
			return
		}
		httpapi.WriteError(w, http.StatusInternalServerError, "CHART_READ_FAILED", "failed to read chart file")
		return
	}

	http.ServeFile(w, r, path)
}

func (h Handler) ChartRunMeta(w http.ResponseWriter, r *http.Request) {
	runID := chi.URLParam(r, "runID")
	if !isSafeSegment(runID) {
		httpapi.WriteError(w, http.StatusBadRequest, "CHART_INVALID_PATH", "invalid chart path")
		return
	}

	path := filepath.Join(h.uploadsDir, "chart-runs", runID, "meta.json")
	raw, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			httpapi.WriteError(w, http.StatusNotFound, "CHART_RUN_NOT_FOUND", "chart run not found")
			return
		}
		httpapi.WriteError(w, http.StatusInternalServerError, "CHART_META_READ_FAILED", "failed to read chart run meta")
		return
	}

	var payload any
	if err := json.Unmarshal(raw, &payload); err != nil {
		httpapi.WriteError(w, http.StatusInternalServerError, "CHART_META_READ_FAILED", "failed to read chart run meta")
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(payload)
}
