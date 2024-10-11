FROM python:3.12
ARG SERVICE_CONTAINER_DIR=/app

# Create app directory
RUN mkdir -p ${SERVICE_CONTAINER_DIR}

# Install system dependencies, including Rust and Cargo
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Rust and Cargo
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

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