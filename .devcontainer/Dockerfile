FROM python:3.10

# Install Jupyter and essential packages
RUN pip install --no-cache-dir \
    jupyter \
    jupyterlab \
    ipykernel \
    notebook \
    jupyter_contrib_nbextensions 

# Create vscode user
RUN groupadd --gid 1000 vscode && \
    useradd --uid 1000 --gid vscode --shell /bin/bash --create-home vscode

# Install devcontainer features
RUN pip install python-dotenv

#########################
### Begin Custom Code ###
#########################

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    unzip \
    git \
    chromium \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install ChromeDriver
RUN CHROME_DRIVER_VERSION=$(curl -sL https://chromedriver.storage.googleapis.com/LATEST_RELEASE) && \
    wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/$CHROME_DRIVER_VERSION/chromedriver_linux64.zip && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin && \
    chmod +x /usr/local/bin/chromedriver && \
    rm /tmp/chromedriver.zip



#######################
### End Custom Code ###
#######################


# Set working directory
WORKDIR /workspace

# Copy requirements.txt and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV PYTHONPATH=/workspace
ENV PATH=$PATH:/usr/local/bin

# Set permissions
RUN chown -R vscode:vscode /workspace

# Switch to vscode user
USER vscode

# Keep the container running
CMD ["tail", "-f", "-n0", "/workspace/.devcontainer.log"]
