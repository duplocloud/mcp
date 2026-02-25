ARG PY_VERSION=3.13

# Stage 1: Install dependencies and build tools
FROM python:${PY_VERSION} AS setup

WORKDIR /app

# Copy the source code
COPY . .

# Install git and build dependencies
RUN <<EOF
apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
pip install --no-cache-dir --upgrade pip
pip install --no-cache-dir .[build]
EOF

# Build the package
FROM setup AS builder
RUN python -m build --no-isolation

# Final stage: Install the package in a slimmer container
FROM python:${PY_VERSION}-slim AS runner

WORKDIR /app

# Copy the built package from the previous stage
COPY --from=builder /app/dist ./dist/

# Install git and the package using pip
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir ./dist/*.whl && \
  rm -rf ./dist

# Set the command to run the server using the CLI command
CMD ["duplocloud-mcp"]
