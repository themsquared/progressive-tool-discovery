FROM python:3.12-slim
WORKDIR /app
COPY catalog_data.py mcp_http.py flat_server.py progressive_server.py ./
# SERVER_SCRIPT and PORT are set per-service in docker-compose.yml.
CMD ["sh", "-c", "python3 ${SERVER_SCRIPT}"]
