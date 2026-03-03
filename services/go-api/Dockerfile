FROM golang:1.24.3-bookworm AS builder

WORKDIR /src/services/go-api

COPY services/go-api/go.mod services/go-api/go.sum ./
RUN export PATH="$PATH:/usr/local/go/bin" && go mod download

COPY services/go-api/ ./
RUN export PATH="$PATH:/usr/local/go/bin" \
    && CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -trimpath -ldflags="-s -w" -o /out/go-api ./cmd/server

FROM alpine:3.20

RUN addgroup -S app && adduser -S -G app app

WORKDIR /app

COPY --from=builder /out/go-api /usr/local/bin/go-api

USER app

EXPOSE 8080

ENV GO_API_ADDR=:8080
ENV DATABASE_URL=postgres://placeholder

ENTRYPOINT ["/usr/local/bin/go-api"]
