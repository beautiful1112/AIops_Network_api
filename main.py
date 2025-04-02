from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
import io
from typing import List, Dict, Optional
import json

app = FastAPI(title="Network Device Upload API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define the expected columns and their default values
REQUIRED_COLUMNS = {
    'device_type': '',
    'host': '',
    'username': '',
    'password': '',
    'port': 22,
    'secret': ''
}

@app.post("/upload/excel")
async def upload_excel(file: UploadFile = File(...)):
    """
    Upload an Excel file containing network device information and convert it to JSON format.
    
    The Excel file should contain the following columns:
    - device_type: Device type (e.g., cisco_ios, junos, etc.)
    - host: IP address
    - username: Username for authentication
    - password: Password for authentication
    - port: SSH port (default: 22)
    - secret: Enable password (optional)
    
    Example Excel format:
    | device_type | host         | username | password | port | secret |
    |------------|--------------|----------|----------|------|---------|
    | cisco_ios  | 192.168.1.1  | admin    | pass123  | 22   | enable  |
    """
    if not file:
        raise HTTPException(
            status_code=400,
            detail="No file uploaded"
        )

    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=400,
            detail="File must be an Excel file (.xlsx or .xls)"
        )
    
    try:
        # Read the Excel file
        contents = await file.read()
        if not contents:
            raise HTTPException(
                status_code=400,
                detail="File is empty"
            )
            
        df = pd.read_excel(io.BytesIO(contents))
        
        # Check if all required columns exist
        missing_columns = [col for col in REQUIRED_COLUMNS.keys() if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing_columns)}"
            )
        
        # Fill missing values with defaults
        for col, default_value in REQUIRED_COLUMNS.items():
            if col not in df.columns:
                df[col] = default_value
            # Replace NaN values with default values
            df[col] = df[col].replace({np.nan: default_value})
        
        # Convert port to integer
        df['port'] = pd.to_numeric(df['port'], errors='coerce').fillna(22).astype(int)
        
        # Replace NaN values with empty strings for text fields
        text_columns = ['device_type', 'host', 'username', 'password', 'secret']
        for col in text_columns:
            df[col] = df[col].replace({np.nan: ''})
        
        # Convert DataFrame to list of dictionaries
        devices = df.to_dict(orient='records')
        
        # Validate required fields
        for i, device in enumerate(devices):
            if not device['host'] or not device['username'] or not device['password']:
                raise HTTPException(
                    status_code=400,
                    detail=f"Row {i+1}: host, username, and password are required fields"
                )
        
        return {
            "filename": file.filename,
            "total_devices": len(devices),
            "devices": devices
        }
    except pd.errors.EmptyDataError:
        raise HTTPException(
            status_code=400,
            detail="The Excel file is empty or contains no data"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing file: {str(e)}"
        )

@app.post("/upload/txt")
async def upload_txt(file: UploadFile = File(...)):
    """
    Upload a TXT file containing network commands and return its parsed contents
    
    The text file should contain one command per line, for example:
    show ip int bri
    show running-config
    show ip route table
    etc.
    """
    if not file:
        raise HTTPException(
            status_code=400,
            detail="No file uploaded"
        )

    if not file.filename.endswith('.txt'):
        raise HTTPException(
            status_code=400,
            detail="File must be a text file (.txt)"
        )
    
    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(
                status_code=400,
                detail="File is empty"
            )

        # Decode and process the commands
        text_content = contents.decode('utf-8').strip()
        commands = [cmd.strip() for cmd in text_content.split('\n') if cmd.strip()]
        
        return {
            "filename": file.filename,
            "total_commands": len(commands),
            "commands": commands
        }
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="File must be a valid text file with UTF-8 encoding"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing file: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 