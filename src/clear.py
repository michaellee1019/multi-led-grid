def create_clear_payload(grid_height: int) -> Dict:
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
        payload[str(strip)] = {
            "set_animation": "solid",
            "color": [0, 0, 0]
        }
    
    return payload


def create_clear_payload_for_components(components: List, index_ranges: List[Tuple[int, int]], 
                                      grid_width: int = 140) -> Dict:
    """
    Create a payload to clear LEDs for specific components using set_animation.
    
    Args:
        components: List of component instances
        index_ranges: List of tuples (start, end) for each component's index range
        grid_width: Width of LED grid in pixels (not used in this implementation)
        
    Returns:
        Dictionary with global indices as keys and set_animation commands
        to turn off LEDs for the specified components
    """
    payload = {}
    
    # For each component's index range
    for component_idx, (start, end) in enumerate(index_ranges):
        # For each global index in this component's range
        for global_index in range(start, end + 1):
            payload[str(global_index)] = {
                "set_animation": "solid",
                "color": [0, 0, 0]
            }
    
    return payload 