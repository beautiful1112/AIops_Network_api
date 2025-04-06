from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
import io
from typing import List, Dict, Optional
import json
import re

app = FastAPI(title="Network Device Configuration API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_command_pairs(df):
    """
    Get all command and description column pairs from the DataFrame.
    Returns a list of tuples (command_column, description_column) in order.
    """
    # Find all command and description columns with more flexible pattern
    command_cols = []
    desc_cols = []
    
    for col in df.columns:
        col_lower = col.lower()
        if 'command' in col_lower and any(str(i) in col_lower for i in range(10)):
            command_cols.append(col)
        elif 'description' in col_lower and any(str(i) in col_lower for i in range(10)):
            desc_cols.append(col)
    
    # Sort them by the number in the column name
    def get_number(col):
        return int(''.join(filter(str.isdigit, col)))
    
    command_cols.sort(key=get_number)
    desc_cols.sort(key=get_number)
    
    # Pair them up
    return list(zip(command_cols, desc_cols))

@app.post("/upload/excel")
async def upload_excel(file: UploadFile = File(...)):
    """
    Upload an Excel file containing network device information and inspection commands.
    The Excel file should contain a single sheet with the following columns:
    - vendor_device_type: Type of device (e.g., cisco_sw, cisco_fw)
    - device_type: Device platform (e.g., Cisco_ios, Cisco_asa)
    - ip_address: Device IP address
    - username: Login username
    - password: Login password
    - port: SSH port (default: 22)
    - command1, command2, command3, etc.: Commands to execute
    - description1, description2, description3, etc.: Descriptions of the commands
    
    Note: You can have any number of command/description pairs.
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
            
        # Read the Excel file
        df = pd.read_excel(io.BytesIO(contents))
        
        # Validate required columns
        required_base_columns = ['vendor_device_type', 'device_type', 'ip_address', 'username', 'password', 'port']
        missing_base_columns = [col for col in required_base_columns if col not in df.columns]
        if missing_base_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required base columns: {', '.join(missing_base_columns)}"
            )
        
        # Get command and description pairs
        command_pairs = get_command_pairs(df)
        
        if not command_pairs:
            raise HTTPException(
                status_code=400,
                detail="No command/description pairs found in the Excel file"
            )
        
        # Process the data
        result = []
        
        for _, row in df.iterrows():
            # Create inspection commands list
            inspection_commands = []
            for cmd_col, desc_col in command_pairs:
                # Only add if both command and description are not empty
                if pd.notna(row[cmd_col]) and str(row[cmd_col]).strip() and \
                   pd.notna(row[desc_col]) and str(row[desc_col]).strip():
                    inspection_commands.append({
                        "command": str(row[cmd_col]).strip(),
                        "description": str(row[desc_col]).strip()
                    })
            
            # Convert port to integer, default to 22 if not specified
            try:
                port = int(row['port']) if pd.notna(row['port']) else 22
            except ValueError:
                port = 22
            
            device_data = {
                "vendor_device_type": str(row['vendor_device_type']).strip(),
                "device_info": {
                    "device_type": str(row['device_type']).strip(),
                    "ip_address": str(row['ip_address']).strip(),
                    "username": str(row['username']).strip(),
                    "password": str(row['password']).strip(),
                    "port": port
                },
                "inspection_commands": inspection_commands
            }
            result.append(device_data)
        
        return {
            "filename": file.filename,
            "total_devices": len(result),
            "total_commands_per_device": len(command_pairs),
            "devices": result
        }
        
    except pd.errors.EmptyDataError:
        raise HTTPException(
            status_code=400,
            detail="The Excel file is empty or contains no data"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid port value: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing file: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 