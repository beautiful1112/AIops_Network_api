from pyats.topology import loader
from pyats.aetest.steps import Steps
from genie.conf.base import Device
from typing import Dict, List, Optional
import json
from fastapi import HTTPException
import logging

# Configure logging
logging.getLogger('pyats').setLevel(logging.INFO)

class DeviceManager:
    def __init__(self):
        self.device_types = {
            'Cisco_ios': 'ios',
            'Cisco_iosxe': 'iosxe',
            'Cisco_asa': 'asa',
            'Cisco_nxos': 'nxos',
            'Juniper': 'junos'
        }
    
    def create_testbed(self, device_info: Dict) -> Dict:
        """Create a pyATS testbed dictionary for the device"""
        device_type = self.device_types.get(device_info['device_type'])
        if not device_type:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported device type: {device_info['device_type']}"
            )
        
        testbed = {
            'devices': {
                device_info['ip_address']: {
                    'type': device_type,
                    'connections': {
                        'cli': {
                            'protocol': 'ssh',
                            'ip': device_info['ip_address'],
                            'port': device_info.get('port', 22),
                            'username': device_info['username'],
                            'password': device_info['password']
                        }
                    },
                    'credentials': {
                        'default': {
                            'username': device_info['username'],
                            'password': device_info['password']
                        }
                    }
                }
            }
        }
        
        if device_info.get('secret'):
            testbed['devices'][device_info['ip_address']]['credentials']['enable'] = {
                'password': device_info['secret']
            }
        
        return testbed
    
    def connect_to_device(self, device_info: Dict) -> Device:
        """Establish connection to network device using pyATS"""
        try:
            # Create testbed
            testbed_dict = self.create_testbed(device_info)
            
            # Load testbed
            testbed = loader.load(testbed_dict)
            
            # Get device
            device = testbed.devices[device_info['ip_address']]
            
            # Connect to device
            device.connect(learn_hostname=True, log_stdout=False)
            
            return device
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to connect to device: {str(e)}"
            )
    
    def execute_commands(self, device_info: Dict, commands: List[str]) -> Dict:
        """Execute commands on device and return responses using pyATS"""
        try:
            device = self.connect_to_device(device_info)
            responses = []
            
            for command in commands:
                try:
                    # Execute command
                    output = device.execute(command)
                    
                    # Parse output if possible
                    try:
                        parsed_output = device.parse(command)
                        responses.append({
                            "command": command,
                            "status": "success",
                            "output": output,
                            "parsed_output": parsed_output
                        })
                    except Exception:
                        # If parsing fails, just return raw output
                        responses.append({
                            "command": command,
                            "status": "success",
                            "output": output
                        })
                        
                except Exception as e:
                    responses.append({
                        "command": command,
                        "status": "error",
                        "error": str(e)
                    })
            
            # Disconnect from device
            device.disconnect()
            
            return {
                "device_info": device_info,
                "command_responses": responses
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error executing commands: {str(e)}"
            )
    
    def process_device_data(self, device_data: Dict) -> Dict:
        """Process device data and execute commands"""
        try:
            # Extract device info and commands
            device_info = device_data['device_info']
            commands = [cmd['command'] for cmd in device_data['inspection_commands']]
            
            # Execute commands and get responses
            result = self.execute_commands(device_info, commands)
            return result
            
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid device data format: {str(e)}"
            ) 