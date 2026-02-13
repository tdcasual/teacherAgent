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
RUN if [ "$APP_TARGET" = "student" ]; then npm run build:student && mv dist-student dist; else npm run build:teacher && mv dist-teacher dist; fi

FROM nginx:alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
RUN chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/log/nginx \
    && touch /var/run/nginx.pid && chown nginx:nginx /var/run/nginx.pid
USER nginx
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
