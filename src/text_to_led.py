from PIL import Image, ImageDraw, ImageFont
import numpy as np
from typing import List, Tuple, Dict, Optional

class TextToLEDConverter:
    def __init__(self, grid_width: int = 140, grid_height: int = 16, font_size: int = 12, font_path: str = "tom-thumb.pil"):
        """
        Initialize the text to LED converter.
        
        Args:
            grid_width: Width of LED grid in pixels
            grid_height: Height of LED grid in pixels  
            font_size: Font size for text rendering (ignored for bitmap fonts)
            font_path: Path to a bitmap font file (.pil)
        """
        self.grid_width = grid_width
        self.grid_height = grid_height
        self.font_size = font_size
        
        # Try to use the tom-thumb.pil bitmap font for crisp, non-antialiased text
        try:
            self.font = ImageFont.load(font_path)
        except Exception as e:
            print(f"Failed to load bitmap font at {font_path}: {e}. Falling back to default bitmap font.")
            self.font = ImageFont.load_default()
        
        # Create a temporary image to measure text
        self.temp_image = Image.new('RGB', (grid_width * 2, grid_height * 2), (0, 0, 0))
        self.draw = ImageDraw.Draw(self.temp_image)
    
    def text_to_pixels(self, text: str, x_offset: int = 0, y_offset: int = 0, 
                      color: Tuple[int, int, int] = (255, 255, 255)) -> List[Dict]:
        """
        Convert text to LED pixel coordinates.
        
        Args:
            text: Text to convert
            x_offset: Horizontal offset from left edge
            y_offset: Vertical offset from top edge
            color: RGB color for the text
            
        Returns:
            List of dictionaries with 'x', 'y', 'color' keys for each pixel
        """
        # Create a new image for this text
        img = Image.new('RGB', (self.grid_width, self.grid_height), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Draw the text
        draw.text((x_offset, y_offset), text, fill=color, font=self.font)
        
        # Convert to numpy array for easier processing
        img_array = np.array(img)
        
        # Find all non-black pixels
        pixels = []
        for y in range(img_array.shape[0]):
            for x in range(img_array.shape[1]):
                pixel_color = img_array[y, x]
                if not np.array_equal(pixel_color, [0, 0, 0]):  # Not black
                    pixels.append({
                        'x': x,
                        'y': y,
                        'color': tuple(pixel_color)
                    })
        
        return pixels
    
    def rotate_coordinates(self, x: int, y: int, angle_degrees: int = 90) -> Tuple[int, int]:
        """
        Rotate coordinates around the center of the grid.
        
        Args:
            x: Original x coordinate
            y: Original y coordinate
            angle_degrees: Rotation angle in degrees (90 = clockwise)
            
        Returns:
            Tuple of (new_x, new_y) coordinates
        """
        import math
        
        # Convert angle to radians
        angle_rad = math.radians(angle_degrees)
        
        # Calculate center of grid
        center_x = self.grid_width // 2
        center_y = self.grid_height // 2
        
        # Translate to origin
        x_rel = x - center_x
        y_rel = y - center_y
        
        # Apply rotation matrix
        # For 90° clockwise: [cos(90°) -sin(90°)] [x] = [0 -1] [x] = [-y]
        #                    [sin(90°)  cos(90°)] [y]   [1  0] [y]   [x]
        new_x_rel = -y_rel
        new_y_rel = x_rel
        
        # Translate back
        new_x = int(new_x_rel + center_x)
        new_y = int(new_y_rel + center_y)
        
        # Ensure coordinates are within bounds
        new_x = max(0, min(self.grid_width - 1, new_x))
        new_y = max(0, min(self.grid_height - 1, new_y))
        
        return new_x, new_y

    def text_to_led_payload(self, text: str, x_offset: int = 0, y_offset: int = 0,
                           color: Tuple[int, int, int] = (255, 255, 255), 
                           rotation: int = 0,
                           x_position: int = 0, y_position: int = 0) -> Dict:
        """
        Convert text to LED payload format compatible with your distributed command function.
        Supports rotation by rotating the entire image, and allows positioning on the grid.
        Args:
            text: Text to convert
            x_offset: Horizontal offset for text in temp image
            y_offset: Vertical offset for text in temp image
            color: RGB color for the text
            rotation: Rotation angle in degrees (0, 90, 180, 270)
            x_position: X position to paste the rotated image on the grid
            y_position: Y position to paste the rotated image on the grid
        Returns:
            Dictionary with global indices (0-15) as keys and set_pixel_colors commands
        """
        # Step 1: Determine text size
        text_width, text_height = self.get_text_dimensions(text)
        padding = 8  # or 2, depending on your font size
        temp_width = text_width + x_offset + padding
        temp_height = text_height + y_offset + padding
        
        # Step 2: Render text to temp image
        temp_img = Image.new('RGB', (temp_width, temp_height), (0, 0, 0))
        draw = ImageDraw.Draw(temp_img)
        draw.text((x_offset, y_offset), text, fill=color, font=self.font)
        
        # Step 3: Rotate temp image if needed
        if rotation == 90:
            temp_img = temp_img.transpose(Image.Transpose.ROTATE_270)
        elif rotation == 180:
            temp_img = temp_img.transpose(Image.Transpose.ROTATE_180)
        elif rotation == 270:
            temp_img = temp_img.transpose(Image.Transpose.ROTATE_90)
        
        # Step 4: Paste temp image onto grid-sized image at (x_position, y_position)
        grid_img = Image.new('RGB', (self.grid_width, self.grid_height), (0, 0, 0))
        grid_img.paste(temp_img, (x_position, y_position))
        
        # Step 5: Extract pixels and build payload
        img_array = np.array(grid_img)
        payload = {}
        for y in range(img_array.shape[0]):
            for x in range(img_array.shape[1]):
                pixel_color = img_array[y, x]
                if not np.array_equal(pixel_color, [0, 0, 0]):
                    strip = y
                    led = x
                    if str(strip) not in payload:
                        payload[str(strip)] = {"set_pixel_colors": {}}
                    payload[str(strip)]["set_pixel_colors"][str(led)] = list(pixel_color)
        return payload
    
    def get_text_dimensions(self, text: str) -> Tuple[int, int]:
        """
        Get the dimensions of rendered text.
        
        Args:
            text: Text to measure
            
        Returns:
            Tuple of (width, height) in pixels
        """
        bbox = self.draw.textbbox((0, 0), text, font=self.font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    
    def center_text(self, text: str) -> Tuple[int, int]:
        """
        Calculate offsets to center text on the LED grid.
        
        Args:
            text: Text to center
            
        Returns:
            Tuple of (x_offset, y_offset) to center the text
        """
        text_width, text_height = self.get_text_dimensions(text)
        x_offset = max(0, (self.grid_width - text_width) // 2)
        y_offset = max(0, (self.grid_height - text_height) // 2)
        return x_offset, y_offset

# Example usage functions
# def display_text_on_led_grid(text: str, components: List, index_ranges: List[Tuple[int, int]],
#                            grid_width: int = 140, grid_height: int = 16,
#                            x_offset: int = 0, y_offset: int = 0,
#                            color: Tuple[int, int, int] = (255, 255, 255)):
#     """
#     Display text on LED grid using the distributed command function.
    
#     Args:
#         text: Text to display
#         components: List of LED components
#         index_ranges: List of index ranges for each component
#         grid_width: Width of LED grid
#         grid_height: Height of LED grid
#         x_offset: Horizontal offset
#         y_offset: Vertical offset
#         color: RGB color
#     """
#     converter = TextToLEDConverter(grid_width, grid_height)
#     payload = converter.text_to_led_payload(text, x_offset, y_offset, color)
    
    # You would call your execute_distributed_command function here
    # await execute_distributed_command(components, payload, index_ranges)
    
#     return payload


# def display_centered_text_on_led_grid(text: str, components: List, index_ranges: List[Tuple[int, int]],
#                                     grid_width: int, grid_height: int,
#                                     color: Tuple[int, int, int]):
#     """
#     Display centered text on LED grid.
#     """
#     converter = TextToLEDConverter(grid_width, grid_height)
#     x_offset, y_offset = converter.center_text(text)
    
#     return display_text_on_led_grid(text, components, index_ranges, grid_width, grid_height,
#                                   x_offset, y_offset, color)
