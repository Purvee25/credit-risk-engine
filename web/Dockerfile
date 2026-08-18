# Credit Risk Decision Engine — frontend (React + Vite -> nginx)

# ---------- build ----------
FROM node:20-alpine AS build

WORKDIR /app

# Install deps from the lockfile first so this layer caches.
COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

# ---------- serve ----------
FROM nginx:1.27-alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
