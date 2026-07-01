# ============================================================
# JurnalMap — Frontend Dockerfile (React / Nginx)
# Multi-stage build: Node.js build → Nginx production serve
# ============================================================

# ============================================================
# Stage 1: Builder — install deps & build static assets
# ============================================================
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json ./
RUN yarn install

# Copy source code
COPY . .

# Build arguments that become env vars at build time
ARG REACT_APP_BACKEND_URL=http://localhost:8001
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL
ENV NODE_ENV=production

# Build the production bundle
RUN yarn build

# ============================================================
# Stage 2: Runtime — minimal Nginx image to serve static files
# ============================================================
FROM nginx:1.27-alpine AS runtime

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy our custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built static files from builder stage
COPY --from=builder /app/build /usr/share/nginx/html

# Create non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup \
    && chown -R appuser:appgroup /usr/share/nginx/html \
    && chown -R appuser:appgroup /var/cache/nginx \
    && chown -R appuser:appgroup /var/log/nginx \
    && touch /var/run/nginx.pid \
    && chown appuser:appgroup /var/run/nginx.pid

EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:80/ | grep -q "html" || exit 1

CMD ["nginx", "-g", "daemon off;"]
