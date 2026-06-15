FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY services/io-plan-admin/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the sync script (imported by main.py)
COPY scripts/io_plan/ /app/scripts/io_plan/

# Copy the service
COPY services/io-plan-admin/main.py /app/main.py

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
