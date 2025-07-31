import asyncio
import os
from datetime import datetime

from threading import Event
from abc import ABC, abstractmethod
from typing import Mapping, Optional, Sequence, List, Dict, Any, Tuple
from typing_extensions import Self

from viam.module.module import Module
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase
from viam.services.generic import Generic
from viam.utils import ValueTypes
from viam import logging
from viam.resource.easy_resource import EasyResource
from text_to_led import TextToLEDConverter

LOGGER = logging.getLogger(__name__)


class MultiLEDGridService(Generic, EasyResource):
    MODEL = "michaellee1019:multi-led-grid:service"

    board_names: List[str] = []
    boards: List[Generic] = []
    grid_width: int = 0
    grid_height: int = 0

    sleep_time: float = 1.0
    text_to_led_converter: TextToLEDConverter

    @classmethod
    def new(
        cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ) -> "MultiLEDGridService":
        return super().new(
            config,
            dependencies,
        )

    @classmethod
    def validate_config(
        cls, config: ComponentConfig
    ) -> Tuple[Sequence[str], Sequence[str]]:
        if "boards" not in config.attributes.fields:
            raise ValueError("boards is required")
        
        boards_field = config.attributes.fields["boards"]
        if not boards_field.HasField("list_value"):
            raise ValueError("boards must be a list")

        cls.board_names = [str(item.string_value) for item in boards_field.list_value.values]

        if "grid_width" not in config.attributes.fields:
            raise ValueError("grid_width is required")
        grid_width_field = config.attributes.fields["grid_width"]
        if not grid_width_field.HasField("number_value"):
            raise ValueError("grid_width must be a number")
        cls.grid_width = int(grid_width_field.number_value)

        if "grid_height" not in config.attributes.fields:
            raise ValueError("grid_height is required")
        grid_height_field = config.attributes.fields["grid_height"]
        if not grid_height_field.HasField("number_value"):
            raise ValueError("grid_height must be a number")
        cls.grid_height = int(grid_height_field.number_value)

        if "sleep_time" in config.attributes.fields:
            sleep_time_field = config.attributes.fields["sleep_time"]
            if not sleep_time_field.HasField("number_value"):
                raise ValueError("sleep_time must be a number")
            cls.sleep_time = float(sleep_time_field.number_value)

        return cls.board_names, []

    def reconfigure(
        self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ):
        LOGGER.debug("reconfiguring...")

        # Log available dependencies for debugging
        LOGGER.debug(f"Available dependencies: {list(dependencies.keys())}")
        
        for board_name in self.board_names:
            resource_name = ResourceName(
                namespace="rdk",
                type="component",
                subtype="generic",
                name=board_name
            )
            try:
                self.boards.append(dependencies[resource_name])
                LOGGER.debug(f"Successfully loaded board: {board_name}")
            except KeyError:
                LOGGER.error(f"Board '{board_name}' not found in dependencies. Available: {list(dependencies.keys())}")
                raise ValueError(f"Board '{board_name}' is not available. Make sure it's properly configured in your robot config.")

        # Get the directory containing this file (src/)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Look for tom-thumb.pil in the same directory as this file
        font_path = os.path.join(current_dir, "tom-thumb.pil")

        self.text_to_led_converter = TextToLEDConverter(
            grid_width=self.grid_height, grid_height=self.grid_width, font_path=font_path
        )

        super().reconfigure(config, dependencies)

        LOGGER.debug("reconfigured")

    def _parse_display_command(self, command_data: dict) -> dict:
        """
        Parse common parameters for text/time display commands.
        
        Returns:
            Dictionary with parsed parameters: x_position, y_position, x_offset, y_offset, color, rotation
        """
        if "x_position" not in command_data or "y_position" not in command_data:
            raise ValueError("x_position and y_position are required")
        
        try:
            x_position = int(command_data["x_position"])
            y_position = int(command_data["y_position"])
        except (ValueError, TypeError):
            raise ValueError("x_position and y_position must be numeric values")

        if "x_offset" not in command_data or "y_offset" not in command_data:
            x_offset = 0
            y_offset = 0
        else:
            try:
                x_offset = int(command_data["x_offset"])
                y_offset = int(command_data["y_offset"])
            except (ValueError, TypeError):
                raise ValueError("x_offset and y_offset must be numeric values")

        if "color" not in command_data:
            color = (255, 255, 255)
        else:
            try:
                color_input = command_data["color"]
                if not isinstance(color_input, (list, tuple)) or len(color_input) != 3:
                    raise ValueError("color must be a list or tuple of 3 values")
                
                # Convert to integers and validate range
                color = tuple(int(c) for c in color_input)
                if not all(0 <= c <= 255 for c in color):
                    raise ValueError("color values must be between 0 and 255")
                    
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid color format: {e}")

        if "rotation" not in command_data:
            rotation = 0
        else:
            try:
                rotation = int(command_data["rotation"])
            except (ValueError, TypeError):
                raise ValueError("rotation must be a numeric value")

        return {
            "x_position": x_position,
            "y_position": y_position,
            "x_offset": x_offset,
            "y_offset": y_offset,
            "color": color,
            "rotation": rotation
        }

    def _get_index_ranges(self) -> List[Tuple[int, int]]:
        """
        Get index ranges for distributing commands across components.
        
        Returns:
            List of (start, end) tuples for each component
        """
        index_ranges = []
        if len(self.boards) >= 1:
            index_ranges.append((0, 7))  # First component always gets strips 0-7
        if len(self.boards) >= 2:
            index_ranges.append((8, self.grid_width - 1))  # Second component gets remaining strips
        # Add more logic here if you have more than 2 components
        return index_ranges

    async def _display_text(self, text: str, params: dict):
        """
        Common logic for displaying text on the LED grid.
        
        Args:
            text: The text to display
            params: Parsed parameters from _parse_display_command
        """
        LOGGER.debug(f"Grid dimensions: width={self.grid_width}, height={self.grid_height}")
        clear_payload = create_clear_payload(self.grid_height)
        LOGGER.debug(f"Clear payload generated with {len(clear_payload)} entries: {list(clear_payload.keys())}")
        
        index_ranges = self._get_index_ranges()
        LOGGER.debug(f"index_ranges={index_ranges} for {len(self.boards)} components")
        LOGGER.debug(f"Executing clear payload for {len(self.boards)} boards")
        await execute_distributed_command(self.boards, clear_payload, index_ranges, self.sleep_time)
        
        LOGGER.debug(f"About to generate text payload with text='{text}', x_pos={params['x_position']}, y_pos={params['y_position']}")
        payload = self.text_to_led_converter.text_to_led_payload(
            text,
            x_offset=params["x_offset"],
            y_offset=params["y_offset"],
            x_position=params["x_position"],
            y_position=params["y_position"],
            color=params["color"],
            rotation=params["rotation"],
        )
        LOGGER.debug(f"Text payload generated with {len(payload)} entries: {list(payload.keys()) if payload else 'EMPTY'}")
        LOGGER.debug(f"Executing text payload for {len(self.boards)} boards")
        await execute_distributed_command(self.boards, payload, index_ranges, self.sleep_time)

    async def do_command(
        self,
        command: Mapping[str, ValueTypes],
        *,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Mapping[str, ValueTypes]:
        LOGGER.debug("do_command called with command: {command}")

        if "text" in command:
            text_command = command["text"]
            params = self._parse_display_command(text_command)
            
            if "text" not in text_command:
                raise ValueError("text is required in text command")
            
            await self._display_text(text_command["text"], params)

        elif "time" in command:
            time_command = command["time"]
            params = self._parse_display_command(time_command)
            
            # Get current time and format as hh"mm" (12-hour format)
            current_time = datetime.now()
            time_text = current_time.strftime("%I%M")  # Format as "1019" for 10:19 AM or PM
            LOGGER.debug(f"Current time formatted as: {time_text}")
            
            await self._display_text(time_text, params)

        # if "clear" in command:
        #     await self.create_clear_payload(self.grid_width, self.grid_height)

        else:
            index_ranges = self._get_index_ranges()
            await execute_distributed_command(self.boards, command, index_ranges, self.sleep_time)

        return {"success": True}


async def execute_distributed_command(components, global_payload, index_ranges, sleep_time=0):
    """
    Execute a command distributed across multiple components sequentially.

    Args:
        components: List of component instances (e.g., [led_col_1, led_col_2])
        global_payload: The overall payload with global indices as keys
        index_ranges: List of tuples (start, end) for each component's index range
        sleep_time: Time to sleep between each component command (default: 0)

    Example:
        components = [led_col_1, led_col_2]
        global_payload = {
            "0": {"set_pixel_colors": {"50": [255, 255, 255]}},
            "8": {"set_pixel_colors": {"51": [255, 255, 255]}}
        }
        index_ranges = [(0, 7), (8, 15)]  # Component 1: 0-7, Component 2: 8-15
    """
    LOGGER.debug(f"execute_distributed_command called with {len(components)} components")
    LOGGER.debug(f"Index ranges: {index_ranges}")
    LOGGER.debug(f"Global payload keys: {list(global_payload.keys())}")
    
    # Group commands by component
    component_commands = {}

    for global_index, command_data in global_payload.items():
        global_index = int(global_index)

        # Find which component this index belongs to
        for component_idx, (start, end) in enumerate(index_ranges):
            if start <= global_index <= end:
                # Calculate relative index for this component
                relative_index = global_index - start

                # Initialize component command if not exists
                if component_idx not in component_commands:
                    component_commands[component_idx] = {}

                # Add command with relative index
                component_commands[component_idx][str(relative_index)] = command_data
                LOGGER.debug(f"Mapped global index {global_index} to component {component_idx}, relative index {relative_index}")
                break

    LOGGER.debug(f"Component commands grouped: {len(component_commands)} components have commands")
    for comp_idx, cmds in component_commands.items():
        LOGGER.debug(f"Component {comp_idx} has {len(cmds)} commands: {list(cmds.keys())}")

    # Execute commands for each component sequentially with sleep delays
    for component_idx, commands in component_commands.items():
        if commands:  # Only execute if there are commands for this component
            component = components[component_idx]
            LOGGER.debug(f"About to execute command for component {component_idx}")
            await component.do_command(commands)
            LOGGER.debug(f"Executed command for component {component_idx}")
            # Sleep between component commands if sleep_time is specified
            if sleep_time > 0:
                LOGGER.debug(f"Sleeping for {sleep_time} seconds")
                await asyncio.sleep(sleep_time)


def create_clear_payload(grid_width: int = 140, grid_height: int = 16):
    """
    Create a payload to clear all LEDs using set_animation with solid black color.

    Args:
        grid_width: Width of LED grid in pixels (not used in this implementation)
        grid_height: Height of LED grid in pixels (number of strips)

    Returns:
        Dictionary with global indices (0-15) as keys and set_animation commands
        to turn off all LEDs with solid black color
    """
    payload = {}

    # For each strip (global index 0-15)
    for strip in range(grid_height):
        payload[str(strip)] = {"set_animation": "solid", "color": [0, 0, 0]}

    return payload


if __name__ == "__main__":
    asyncio.run(Module.run_from_registry())
