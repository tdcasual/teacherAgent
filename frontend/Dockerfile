FROM node:24-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi
COPY frontend/ ./
ARG VITE_API_URL
ARG VITE_MCP_URL
ARG APP_TARGET=teacher
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_MCP_URL=$VITE_MCP_URL
RUN test -n "$VITE_API_URL" || (echo "VITE_API_URL is required" >&2 && exit 1)
RUN node -e 'process.stdout.write(new URL(process.env.VITE_API_URL).origin)' > /tmp/api_origin
RUN if [ "$APP_TARGET" = "student" ]; then npm run build:student && mv dist-student dist; else npm run build:teacher && mv dist-teacher dist; fi

FROM nginx:alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /tmp/api_origin /tmp/api_origin
COPY --from=build /app/dist /usr/share/nginx/html
RUN API_ORIGIN="$(cat /tmp/api_origin)" \
    && test -n "$API_ORIGIN" \
    && sed -i "s|__API_ORIGIN__|${API_ORIGIN}|g" /etc/nginx/conf.d/default.conf \
    && chmod 644 /etc/nginx/conf.d/default.conf \
    && rm -f /tmp/api_origin \
    && if grep -qF "__API_ORIGIN__" /etc/nginx/conf.d/default.conf; then echo "failed to bake API origin" >&2; exit 1; fi
RUN chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/log/nginx \
    && touch /var/run/nginx.pid && chown nginx:nginx /var/run/nginx.pid
USER nginx
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
