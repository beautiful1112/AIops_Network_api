from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
import io
from typing import List, Dict, Optional
import json
import re
from device_manager import DeviceManager

app = FastAPI(title="Network Device Configuration API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize device manager
device_manager = DeviceManager()

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
    The Excel file should contain two sheets:
    
    1. "Devices" sheet with columns:
    - vendor_device_type: Type of device (e.g., cisco_sw, cisco_fw)
    - device_type: Device platform (e.g., Cisco_ios, Cisco_asa)
    - ip_address: Device IP address
    - username: Login username
    - password: Login password
    - port: SSH port (default: 22)
    
    2. "Commands" sheet with columns:
    - device_type: Device platform (e.g., Cisco_ios, Cisco_asa)
    - command: Command to execute
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
            
        # Read both sheets
        devices_df = pd.read_excel(io.BytesIO(contents), sheet_name='Devices')
        commands_df = pd.read_excel(io.BytesIO(contents), sheet_name='Commands')
        
        # Validate required columns in Devices sheet
        required_device_columns = ['vendor_device_type', 'device_type', 'ip_address', 'username', 'password', 'port']
        missing_device_columns = [col for col in required_device_columns if col not in devices_df.columns]
        if missing_device_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns in Devices sheet: {', '.join(missing_device_columns)}"
            )
        
        # Validate required columns in Commands sheet
        required_command_columns = ['device_type', 'command']
        missing_command_columns = [col for col in required_command_columns if col not in commands_df.columns]
        if missing_command_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns in Commands sheet: {', '.join(missing_command_columns)}"
            )
        
        # Process the data
        result = []
        
        # Group commands by device_type
        commands_by_type = commands_df.groupby('device_type')
        
        for _, device_row in devices_df.iterrows():
            device_type = device_row['device_type']
            
            # Get commands for this device type
            device_commands = []
            if device_type in commands_by_type.groups:
                commands = commands_by_type.get_group(device_type)
                for _, cmd_row in commands.iterrows():
                    if pd.notna(cmd_row['command']):
                        device_commands.append({
                            "command": str(cmd_row['command']).strip()
                        })
            
            # Convert port to integer, default to 22 if not specified
            try:
                port = int(device_row['port']) if pd.notna(device_row['port']) else 22
            except ValueError:
                port = 22
            
            device_data = {
                "vendor_device_type": str(device_row['vendor_device_type']).strip(),
                "device_info": {
                    "device_type": str(device_row['device_type']).strip(),
                    "ip_address": str(device_row['ip_address']).strip(),
                    "username": str(device_row['username']).strip(),
                    "password": str(device_row['password']).strip(),
                    "port": port
                },
                "inspection_commands": device_commands
            }
            result.append(device_data)
        
        return {
            "filename": file.filename,
            "total_devices": len(result),
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

@app.post("/execute/commands")
async def execute_commands(device_data: Dict):
    """
    Execute commands on network devices and return responses.
    
    Expected JSON format:
    {
        "vendor_device_type": "cisco_sw",
        "device_info": {
            "device_type": "ios",  # Direct device type: ios, iosxe, asa, nxos, junos
            "ip_address": "192.168.1.1",
            "username": "admin",
            "password": "cisco123",
            "port": 22
        },
        "inspection_commands": [
            {"command": "show version"},
            {"command": "show running-config"}
        ]
    }
    """
    try:
        # Process device data and execute commands
        result = device_manager.process_device_data(device_data)
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing device data: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 