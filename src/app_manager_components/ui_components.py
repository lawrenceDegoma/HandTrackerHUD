"""
UI Components and Text Utilities

This module handles text processing, scrolling animations, and UI helper functions
that are used across different parts of the application.
"""

import cv2
import numpy as np
import unicodedata
import time


class TextRenderer:
    """Handles text rendering with scrolling and Unicode support."""
    
    def __init__(self):
        self.scroll_state = {}  # Track scrolling state for each text field
    
    def clean_text_for_display(self, text):
        """Clean text to handle Unicode characters properly for OpenCV display."""
        if not text:
            return ""
        
        # Replace common problematic Unicode characters
        replacements = {
            '\u2019': "'",  # Right single quotation mark
            '\u2018': "'",  # Left single quotation mark
            '\u201c': '"',  # Left double quotation mark
            '\u201d': '"',  # Right double quotation mark
            '\u2013': '-',  # En dash
            '\u2014': '-',  # Em dash
            '\u2026': '...',  # Horizontal ellipsis
            '\u00e9': 'e',  # é
            '\u00e8': 'e',  # è
            '\u00ea': 'e',  # ê
            '\u00e1': 'a',  # á
            '\u00e0': 'a',  # à
            '\u00f1': 'n',  # ñ
            '\u00fc': 'u',  # ü
            '\u00f6': 'o',  # ö
            '\u00e4': 'a',  # ä
        }
        
        # Apply replacements
        for unicode_char, replacement in replacements.items():
            text = text.replace(unicode_char, replacement)
        
        # Normalize Unicode characters and remove any remaining non-ASCII characters
        try:
            # Normalize to decomposed form, then remove combining characters
            text = unicodedata.normalize('NFKD', text)
            # Keep only ASCII characters
            text = text.encode('ascii', 'ignore').decode('ascii')
        except Exception:
            # Fallback: remove any non-printable characters
            text = ''.join(char for char in text if ord(char) < 128 and char.isprintable())
        
        return text
    
    def get_scrolling_text(self, text, field_name, max_width, font_scale=0.6):
        """Handle horizontal scrolling text for long titles/artists."""
        if not text:
            return text, 0
        
        # Calculate text width
        (text_width, text_height), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 2)
        
        # If text fits within the available space, no scrolling needed
        if text_width <= max_width:
            # Reset scroll state if text fits
            if field_name in self.scroll_state:
                del self.scroll_state[field_name]
            return text, 0
        
        # Initialize scroll state for this field if not exists
        if field_name not in self.scroll_state:
            self.scroll_state[field_name] = {
                'start_time': time.time(),
                'text': text,
                'pause_start': 0,
                'pause_end': 2.0,  # Pause at start for 2 seconds
                'scroll_speed': 30,  # pixels per second
                'text_width': text_width,
                'max_width': max_width
            }
        
        state = self.scroll_state[field_name]
        current_time = time.time()
        elapsed_time = current_time - state['start_time']
        
        # If text changed, reset the scroll state
        if state['text'] != text:
            state['start_time'] = current_time
            state['text'] = text
            state['text_width'] = text_width
            state['pause_start'] = 0
            state['pause_end'] = 2.0
            elapsed_time = 0
        
        # Phase 1: Pause at start (show beginning of text)
        if elapsed_time <= state['pause_end']:
            return text, 0
        
        # Phase 2: Scroll from right to left
        scroll_duration = (state['text_width'] - state['max_width'] + 40) / state['scroll_speed']  # +40 for spacing
        scroll_phase_end = state['pause_end'] + scroll_duration
        
        if elapsed_time <= scroll_phase_end:
            # Calculate scroll offset
            scroll_progress = (elapsed_time - state['pause_end']) / scroll_duration
            scroll_offset = -int(scroll_progress * (state['text_width'] - state['max_width'] + 40))
            return text, scroll_offset
        
        # Phase 3: Pause at end (show end of text)
        pause_at_end = 1.5
        if elapsed_time <= scroll_phase_end + pause_at_end:
            scroll_offset = -(state['text_width'] - state['max_width'] + 40)
            return text, scroll_offset
        
        # Phase 4: Reset and start over
        state['start_time'] = current_time
        return text, 0
    
    def draw_scrolling_text(self, img, text, field_name, x, y, max_width, font_scale, color, thickness=2):
        """Draw text with horizontal scrolling if it's too long."""
        display_text, scroll_offset = self.get_scrolling_text(text, field_name, max_width, font_scale)
        
        if scroll_offset == 0:
            # No scrolling needed or at start position
            cv2.putText(img, display_text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
        else:
            # Create a temporary image for the scrolling text
            temp_img = np.zeros_like(img)
            
            # Draw text with offset on temporary image
            text_x = x + scroll_offset
            cv2.putText(temp_img, display_text, (text_x, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
            
            # Create a mask for the clipping region
            mask = np.zeros(img.shape[:2], dtype=np.uint8)
            cv2.rectangle(mask, (x, y-25), (x+max_width, y+5), 255, -1)
            
            # Apply the mask to the temporary image
            temp_img_masked = cv2.bitwise_and(temp_img, temp_img, mask=mask)
            
            # Clear the text area on the original image
            img_mask_inv = cv2.bitwise_not(mask)
            img_cleared = cv2.bitwise_and(img, img, mask=img_mask_inv)
            
            # Combine the cleared original with the masked text
            img[:] = cv2.add(img_cleared, temp_img_masked)
        
        return img


def format_time(seconds):
    """Format seconds into MM:SS format."""
    mins = seconds // 60
    secs = seconds % 60
    return f"{mins}:{secs:02d}"
