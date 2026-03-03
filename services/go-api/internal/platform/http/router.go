package httpapi

import (
	"net/http"

	"github.com/go-chi/chi/v5"
)

func NewRouter() http.Handler {
	r := chi.NewRouter()
	r.Get("/healthz", HealthHandler)
	r.Get("/health", HealthHandler)
	return r
}
