# Network Device Configuration API

A FastAPI-based API for handling network device configurations and commands.

## Features

- Excel file upload for network device configurations
  - Supports device information including device type, host, username, password, port, and secret
  - Validates required fields and data formats
  - Converts Excel data to JSON format

- Text file upload for network commands
  - Supports multiple commands in a single file
  - Returns parsed commands in JSON format
  - Handles common network show commands

## Installation

1. Clone the repository:
```bash
git clone <your-repository-url>
cd AIops_network_api
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the server:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

2. Access the API documentation:
- OpenAPI documentation: http://localhost:8000/docs
- ReDoc documentation: http://localhost:8000/redoc

## API Endpoints

### 1. Upload Excel File
- **Endpoint**: `/upload/excel`
- **Method**: POST
- **Content-Type**: multipart/form-data
- **Parameters**: file (Excel file)
- **Expected Excel Format**:
  ```
  | device_type | host         | username | password | port | secret |
  |------------|--------------|----------|----------|------|---------|
  | cisco_ios  | 192.168.1.1  | admin    | pass123  | 22   | enable  |
  ```

### 2. Upload Text File
- **Endpoint**: `/upload/txt`
- **Method**: POST
- **Content-Type**: multipart/form-data
- **Parameters**: file (Text file)
- **Example Content**:
  ```
  show ip int bri
  show running-config
  show ip route table
  show mac database
  show ip ospf bri
  ```

## Requirements

- Python 3.7+
- FastAPI
- pandas
- openpyxl
- python-multipart
- uvicorn 