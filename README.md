# Rentlora Property Service

This service handles the creation and viewing of properties for the Rentlora platform.

## Technology Stack
- FastAPI
- Motor (Async MongoDB)
- Uvicorn

## Environment Variables
- `MONGO_USER` (optional)
- `MONGO_PASSWORD` (optional)
- `MONGO_HOST` (default: `localhost`)
- `MONGO_PORT` (default: `27017`)
- `PORT` (default: `8002`)

## Running Locally

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the service:
   ```bash
   python -m src.main
   ```

## Running with Docker

1. Build the image:
   ```bash
   docker build -t rentlora-property-service .
   ```

2. Run the container:
   ```bash
   docker run -p 8002:8002 -e MONGO_HOST="host.docker.internal" rentlora-property-service
   ```
