FROM rust:1.75-slim AS builder

WORKDIR /app
COPY Cargo.toml .
COPY src/ ./src/

RUN cargo build --release

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y ca-certificates curl && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/target/release/pythguard-reader /usr/local/bin/pythguard-reader

EXPOSE 8001

CMD ["pythguard-reader"]
