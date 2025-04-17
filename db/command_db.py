import json
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class CommandDB:
    def __init__(self, db_file: str = "commands.json"):
        """Initialize the command database using JSON file storage."""
        # Get the absolute path to the server directory
        server_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_file = os.path.join(server_dir, db_file)
        self._init_db()
        log.info(f"Command database initialized using JSON file: {self.db_file}")

    def _init_db(self):
        """Initialize the JSON database file if it doesn't exist."""
        try:
            if not os.path.exists(self.db_file):
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
                with open(self.db_file, 'w') as f:
                    json.dump({
                        "commands": [],
                        "last_command": None
                    }, f, indent=2)
                log.info(f"Created new command database file: {self.db_file}")
            else:
                log.info(f"Using existing command database file: {self.db_file}")
        except Exception as e:
            log.error(f"Error initializing database file: {e}")
            raise

    def _read_db(self) -> Dict:
        """Read the entire database from the JSON file."""
        try:
            with open(self.db_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            log.error(f"Error reading database file: {e}")
            return {"commands": [], "last_command": None}

    def _write_db(self, data: Dict):
        """Write data to the JSON database file."""
        try:
            with open(self.db_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log.error(f"Error writing to database file: {e}")

    def add_command(self, command_data: Dict) -> Optional[int]:
        """Add a new command to the database and update last command."""
        try:
            data = self._read_db()
            command_data['timestamp'] = datetime.now().isoformat()
            
            # Generate a new ID if not provided
            if 'id' not in command_data:
                # Find the highest existing ID and increment it
                max_id = max([cmd.get('id', 0) for cmd in data['commands']], default=0)
                command_data['id'] = max_id + 1
            
            data['commands'].append(command_data)
            
            # Update last command
            data['last_command'] = {
                'id': command_data['id'],
                'command': command_data.get('command'),
                'type': command_data.get('type'),
                'timestamp': command_data['timestamp']
            }
            
            self._write_db(data)
            log.info(f"Added new command with ID {command_data['id']}: {command_data}")
            return command_data['id']
        except Exception as e:
            log.error(f"Error adding command: {e}")
            return None

    def update_command_status(self, command_id: int, new_status: str, details: Optional[Dict] = None) -> bool:
        """Update the status of a command."""
        try:
            data = self._read_db()
            for cmd in data['commands']:
                if cmd.get('id') == command_id:
                    cmd['status'] = new_status
                    cmd['last_updated'] = datetime.now().isoformat()
                    if details:
                        cmd['details'] = details
                    self._write_db(data)
                    log.info(f"Updated command {command_id} status to {new_status}")
                    return True
            log.warning(f"Command {command_id} not found for status update")
            return False
        except Exception as e:
            log.error(f"Error updating command status: {e}")
            return False

    def get_command_status(self, command_id: int) -> Optional[str]:
        """Get the status of a command."""
        try:
            data = self._read_db()
            for cmd in data['commands']:
                if cmd.get('id') == command_id:
                    return cmd.get('status')
            log.warning(f"Command {command_id} not found")
            return None
        except Exception as e:
            log.error(f"Error getting command status: {e}")
            return None

    def get_pending_commands(self) -> List[Dict]:
        """Get all pending commands."""
        try:
            data = self._read_db()
            pending = [cmd for cmd in data['commands'] if cmd.get('status') == 'pending']
            log.info(f"Found {len(pending)} pending commands")
            return pending
        except Exception as e:
            log.error(f"Error getting pending commands: {e}")
            return []

    def get_command_by_id(self, command_id: int) -> Optional[Dict]:
        """Get a command by its ID."""
        try:
            data = self._read_db()
            for cmd in data['commands']:
                if cmd.get('id') == command_id:
                    return cmd
            log.warning(f"Command {command_id} not found")
            return None
        except Exception as e:
            log.error(f"Error getting command by ID: {e}")
            return None

    def delete_command(self, command_id: int) -> bool:
        """Delete a command from the database."""
        try:
            data = self._read_db()
            initial_length = len(data['commands'])
            data['commands'] = [cmd for cmd in data['commands'] if cmd.get('id') != command_id]
            if len(data['commands']) < initial_length:
                self._write_db(data)
                log.info(f"Deleted command {command_id}")
                return True
            log.warning(f"Command {command_id} not found for deletion")
            return False
        except Exception as e:
            log.error(f"Error deleting command: {e}")
            return False

    def get_last_command(self) -> Optional[Dict]:
        """Get the last executed command."""
        try:
            data = self._read_db()
            return data.get('last_command')
        except Exception as e:
            log.error(f"Error getting last command: {e}")
            return None

    def is_last_command_ping(self) -> bool:
        """Check if the last command was a ping command."""
        last_command = self.get_last_command()
        return last_command is not None and last_command.get('type') == 'ping'

    def is_last_command_pingall(self) -> bool:
        """Check if the last command was a pingall command."""
        last_command = self.get_last_command()
        return last_command is not None and last_command.get('type') == 'pingall'

# Create a global instance
command_db = CommandDB() 