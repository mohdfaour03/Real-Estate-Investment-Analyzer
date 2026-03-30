# ── Frontend (React + Vite → Nginx) ──
# Multi-stage build: build JS bundle, then serve with Nginx

# Stage 1 — Build the React app
FROM node:20-alpine AS build

WORKDIR /app

# Copy package manifests first (layer caching — only re-install if deps change)
COPY package.json package-lock.json* ./
RUN npm ci --production=false

# Copy source and build the production bundle
COPY . .
RUN npm run build

# Stage 2 — Serve static files with Nginx
FROM nginx:alpine

# Custom Nginx config: SPA routing + API reverse proxy
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from Stage 1
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

# Healthcheck — verify Nginx is serving
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget -qO- http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
