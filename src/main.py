import asyncio

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

    sleep_time: float = 0.75
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
        if "boards" not in config.attributes:
            raise ValueError("boards is required")
        if not isinstance(config.attributes["boards"], list):
            raise ValueError("boards must be a list")

        cls.board_names = config.attributes.fields["boards"].list_value

        if "grid_width" not in config.attributes:
            raise ValueError("grid_width is required")
        if not isinstance(config.attributes["grid_width"], int):
            raise ValueError("grid_width must be an integer")
        cls.grid_width = config.attributes["grid_width"]

        if "grid_height" not in config.attributes:
            raise ValueError("grid_height is required")
        if not isinstance(config.attributes["grid_height"], int):
            raise ValueError("grid_height must be an integer")
        cls.grid_height = config.attributes["grid_height"]

        return [cls.board_names], []

    def reconfigure(
        self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ):
        for board_name in self.board_names:
            self.boards.append(dependencies[board_name])

        self.text_to_led_converter = TextToLEDConverter(
            grid_width=self.grid_width, grid_height=self.grid_height
        )

        LOGGER.info("reconfigure called")
        super().reconfigure(config, dependencies)

    async def do_command(
        self,
        command: Mapping[str, ValueTypes],
        *,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Mapping[str, ValueTypes]:
        LOGGER.info("do_command called with command: {command}")

        if "text" in command:
            text = command["text"]

            if "x_position" not in command or "y_position" not in command:
                raise ValueError("x_position and y_position are required")
            if not isinstance(command["x_position"], int) or not isinstance(command["y_position"], int):
                raise ValueError("x_position and y_position must be integers")

            if "x_offset" not in command or "y_offset" not in command:
                x_offset = 0
                y_offset = 0
            elif not isinstance(command["x_offset"], int) or not isinstance(command["y_offset"], int):
                raise ValueError("x_offset and y_offset must be integers")
            else:
                x_offset = command["x_offset"]
                y_offset = command["y_offset"]
            
            if "color" not in command:
                color = (255, 255, 255)
            elif not isinstance(command["color"], tuple) or len(command["color"]) != 3:
                raise ValueError("color must be a tuple of 3 integers")
            else:
                color = command["color"]

            if "rotation" not in command:
                rotation = 0
            elif not isinstance(command["rotation"], int):
                raise ValueError("rotation must be an integer")
            else:
                rotation = command["rotation"]

            clear_payload = create_clear_payload(self.grid_height)
            await execute_distributed_command(self.boards, clear_payload, index_ranges)
            await asyncio.sleep(self.sleep_time)
            payload = self.text_to_led_converter.text_to_led_payload(
                text,
                x_offset=x_offset,
                y_offset=y_offset,
                x_position=command["x_position"],
                y_position=command["y_position"],
                color=color,
                rotation=rotation,
            )
            await execute_distributed_command(self.boards, payload, index_ranges)
        # if "clear" in command:
        #     await self.create_clear_payload(self.grid_width, self.grid_height)

        else:
            await execute_distributed_command(self.boards, command, index_ranges)

        await asyncio.sleep(self.sleep_time)
        return {"success": True}


async def execute_distributed_command(components, global_payload, index_ranges):
    """
    Execute a command distributed across multiple components.

    Args:
        components: List of component instances (e.g., [led_col_1, led_col_2])
        global_payload: The overall payload with global indices as keys
        index_ranges: List of tuples (start, end) for each component's index range

    Example:
        components = [led_col_1, led_col_2]
        global_payload = {
            "0": {"set_pixel_colors": {"50": [255, 255, 255]}},
            "8": {"set_pixel_colors": {"51": [255, 255, 255]}}
        }
        index_ranges = [(0, 7), (8, 15)]  # Component 1: 0-7, Component 2: 8-15
    """
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
                break

    # Execute commands for each component
    tasks = []
    for component_idx, commands in component_commands.items():
        if commands:  # Only execute if there are commands for this component
            component = components[component_idx]
            task = component.do_command(commands)
            tasks.append(task)

    # Execute all commands concurrently
    if tasks:
        await asyncio.gather(*tasks)


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
