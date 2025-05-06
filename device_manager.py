from pyats.topology import loader
from pyats.aetest.steps import Steps
from genie.conf.base import Device
from typing import Dict, List, Optional
import json
from fastapi import HTTPException
import logging
from netmiko import ConnectHandler
from netmiko.exceptions import NetMikoTimeoutException, NetMikoAuthenticationException

# Configure logging
logging.getLogger('pyats').setLevel(logging.INFO)

class DeviceManager:
    def __init__(self):
        pass
    
    def create_testbed(self, device_info: Dict) -> Dict:
        """Create a pyATS testbed dictionary for the device"""
        os_type = device_info['os_type']
        
        testbed = {
            'devices': {
                device_info['ip_address']: {
                    'type': os_type,
                    'os': os_type,
                    'platform': os_type,
                    'connections': {
                        'cli': {
                            'protocol': 'ssh',
                            'ip': device_info['ip_address'],
                            'port': device_info.get('port', 22),
                            'username': device_info['username'],
                            'password': device_info['password'],
                            'ssh_options': '-o KexAlgorithms=diffie-hellman-group-exchange-sha1,diffie-hellman-group14-sha1 -o HostKeyAlgorithms=ssh-rsa -o Ciphers=aes128-ctr,aes192-ctr,aes256-ctr'
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
            logging.info(f"Created testbed configuration: {json.dumps(testbed_dict, indent=2)}")
            
            # Load testbed
            testbed = loader.load(testbed_dict)
            
            # Get device
            device = testbed.devices[device_info['ip_address']]
            
            # Connect to device
            device.connect(learn_hostname=True, log_stdout=True)
            
            return device
            
        except Exception as e:
            logging.error(f"Failed to connect to device: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to connect to device: {str(e)}"
            )

    def connect_huawei_device(self, device_info: Dict) -> ConnectHandler:
        """Establish connection to Huawei device using Netmiko"""
        try:
            # Map Huawei OS types to Netmiko device types
            os_type = device_info['os_type'].lower()
            if 'vrpv8' in os_type:
                device_type = 'huawei_vrpv8'
            elif 'vrp' in os_type:
                device_type = 'huawei'
            else:
                device_type = 'huawei'

            # Create Netmiko connection parameters
            netmiko_params = {
                'device_type': device_type,
                'host': device_info['ip_address'],
                'username': device_info['username'],
                'password': device_info['password'],
                'port': device_info.get('port', 22),
                'timeout': 30,
                'session_log': f"/tmp/{device_info['ip_address']}-netmiko.log"
            }

            # Establish connection
            connection = ConnectHandler(**netmiko_params)
            return connection

        except NetMikoTimeoutException:
            raise HTTPException(
                status_code=500,
                detail=f"Connection timed out to device {device_info['ip_address']}"
            )
        except NetMikoAuthenticationException:
            raise HTTPException(
                status_code=500,
                detail=f"Authentication failed for device {device_info['ip_address']}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to connect to Huawei device: {str(e)}"
            )
    
    def execute_commands(self, device_info: Dict, commands: List[str]) -> Dict:
        """Execute commands on device and return responses"""
        try:
            # Check if device is Huawei
            is_huawei = any(os_type in device_info['os_type'].lower() for os_type in ['huawei', 'vrp', 'vrpv8'])
            
            if is_huawei:
                # Use Netmiko for Huawei devices
                device = self.connect_huawei_device(device_info)
                responses = []
                
                for command in commands:
                    try:
                        # Execute command
                        output = device.send_command(command)
                        
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
                
            else:
                # Use pyATS for other devices
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