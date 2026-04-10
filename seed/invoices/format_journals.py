#!/usr/bin/env python3
"""
Script to format all journal files to have a maximum of 80 characters per line.
Uses strict hard wrapping to ensure no line exceeds 80 characters.
"""

import os
import re

def wrap_line_strict_80(text: str) -> list:
    """
    Wrap text to strict maximum of 80 characters per line.
    Breaks on word boundaries when possible.
    """
    lines = []
    words = text.split()
    current_line = ""
    
    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        
        if len(test_line) <= 80:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    
    if current_line:
        lines.append(current_line)
    
    return lines

def format_journal_file(file_path: str) -> str:
    """Format a journal file to have maximum 80 characters per line."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    formatted_lines = []
    
    for line in lines:
        line = line.rstrip()
        
        # Handle empty lines
        if not line.strip():
            formatted_lines.append('')
            continue
        
        # If line is already 80 characters or less, keep it
        if len(line) <= 80:
            formatted_lines.append(line)
        else:
            # Wrap the long line
            wrapped = wrap_line_strict_80(line)
            formatted_lines.extend(wrapped)
    
    return '\n'.join(formatted_lines)

def process_all_journal_files():
    """Process all journal files in the daily-journal directory."""
    journal_dir = "seed/invoices/daily-journal"
    
    if not os.path.exists(journal_dir):
        print(f"Error: Directory {journal_dir} does not exist")
        return
    
    txt_files = sorted([f for f in os.listdir(journal_dir) if f.endswith('.txt')])
    
    for txt_file in txt_files:
        file_path = os.path.join(journal_dir, txt_file)
        
        try:
            print(f"Formatting {txt_file}...")
            formatted_content = format_journal_file(file_path)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(formatted_content)
            
            print(f"✓ Formatted {txt_file}")
            
        except Exception as e:
            print(f"✗ Error formatting {txt_file}: {str(e)}")

if __name__ == "__main__":
    process_all_journal_files()
    print("\nAll journal files have been formatted to 80 characters per line.")