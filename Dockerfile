FROM python:3.13
ARG SERVICE_CONTAINER_DIR=/app

# Create app directory
RUN mkdir -p ${SERVICE_CONTAINER_DIR}

# Install Python dependencies
RUN pip install --upgrade pip

# Copy code and configs
COPY requirements/requirements.txt ${SERVICE_CONTAINER_DIR}/requirements.txt
RUN pip install --no-deps -r /app/requirements.txt

COPY . ${SERVICE_CONTAINER_DIR}
WORKDIR ${SERVICE_CONTAINER_DIR}

# Install Gunicorn
RUN pip install gunicorn

# Set the default command to run Gunicorn
CMD ["gunicorn", "app.main:app", "-c", "gunicorn_config.py"]