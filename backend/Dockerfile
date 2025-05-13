# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the dependencies file to the working directory
COPY backend/requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the content of the local src directory to the working directory
COPY backend/app /app/app

# Make port 5167 available to the world outside this container
EXPOSE 5167

# Define environment variable
ENV MODULE_NAME="app.main"
ENV VARIABLE_NAME="app"
ENV APP_PORT="5167"

# Run app.main:app when the container launches
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5167"]