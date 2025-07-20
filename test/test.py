import asyncio
import string
import random
import argparse

from viam.robot.client import RobotClient
from viam.components.generic import Generic
from src.main import execute_distributed_command, create_clear_payload
from src.text_to_led import TextToLEDConverter


async def connect(address: str, api_key: str, api_key_id: str):
    opts = RobotClient.Options.with_api_key(
        api_key=api_key,
        api_key_id=api_key_id,
    )
    return await RobotClient.at_address(address, opts)


async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='LED Wall Text Display')
    parser.add_argument('--api-key', required=True, help='Viam API key')
    parser.add_argument('--api-key-id', required=True, help='Viam API key ID')
    parser.add_argument('--address', required=True, help='Robot address')
    args = parser.parse_args()

    sleep_time = .75
    machine = await connect(args.address, args.api_key, args.api_key_id)

    # For a 16x140 LED grid, you need 16 components (one per strip)
    # Each component handles indices 0-139 internally
    led_col_1 = Generic.from_robot(machine, "led-col-1")
    led_col_2 = Generic.from_robot(machine, "led-col-2")
    
    # Example: Using the distributed command function
    # Global indices 0-15 map to different components
    components = [led_col_1, led_col_2]
    index_ranges = [(0, 7), (8, 15)]  # Component 1: 0-7, Component 2: 8-15
    
    # Clear the display first
    print("Clearing display...")
    clear_payload = create_clear_payload(grid_width=140, grid_height=16)
    print("Clear payload:")
    print(clear_payload)
    await execute_distributed_command(components, clear_payload, index_ranges)
    await asyncio.sleep(sleep_time)
    print("Display cleared")


    # # Example 1: Simple pixel commands (your original example)
    # global_payload = {
    #     "0": {
    #         "set_pixel_colors": {"40": [255, 255, 255], "51": [255, 255, 255]}
    #     },
    #     "8": {
    #         "set_pixel_colors": {"40": [255, 255, 255], "51": [255, 255, 255]}
    #     }
    # }
    
    # # Execute the distributed command
    # await execute_distributed_command(components, global_payload, index_ranges)
    
    # Example 2: Display text on LED grid
    # Create text converter for 16x140 grid
    converter = TextToLEDConverter(grid_width=140, grid_height=16, font_size=20)
    
    # Create a list of characters: 0-9, A-Z, a-z
    chars = list(string.digits + string.ascii_uppercase + string.ascii_lowercase)
    x_pos = 120
    y_pos = 2

    for char in chars:
        # Clear LEDs before displaying the next character
        clear_payload = create_clear_payload(grid_width=140, grid_height=16)
        await execute_distributed_command(components, clear_payload, index_ranges)
        await asyncio.sleep(sleep_time)

        text_payload = converter.text_to_led_payload(
            char+char+char,
            x_offset=0, y_offset=5,
            x_position=x_pos, y_position=y_pos,
            color=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)), rotation=90
        )
        print(f"Displaying {char} at {x_pos}")
        await execute_distributed_command(components, text_payload, index_ranges)
        await asyncio.sleep(sleep_time)

    # Don't forget to close the machine when you're done!
    await machine.close()


if __name__ == "__main__":
    asyncio.run(main())
