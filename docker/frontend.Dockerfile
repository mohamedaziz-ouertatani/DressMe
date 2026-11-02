# The frontend's environment: Node 24 + the npm packages of frontend/package-lock.json.
# They are installed in /app/node_modules, one folder above the mounted frontend/, so
# the PC's own frontend/node_modules (built for Windows) is never used here: Node looks
# for packages in the parent folders too.
# exact Node + Debian release, so every rebuild starts from the same system
FROM node:24.22.1-bookworm-slim
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
WORKDIR /app/frontend
CMD ["/app/node_modules/.bin/vite", "--host", "0.0.0.0"]
