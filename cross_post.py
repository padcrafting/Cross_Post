#!/usr/bin/env python3
"""
Cross-platform posting script for Bluesky and Mastodon.
Meant to be used on a unix-like CLI environment. 
Made by @padcrafting - padcrafting.com

This script posts text (and optionally an image) to both Bluesky and Mastodon
using their respective CLI tools (bsky and toot). It includes an option to edit
the text in nano before posting.

Installation Requirements:
- Python 3.x (standard library only - no external dependencies)
- bsky CLI tool (https://github.com/harveyrandall/bsky-cli)
- toot CLI tool (https://github.com/ihabunek/toot)
- nano editor (typically pre-installed on Unix-like systems)

The tools must be installed and available in the system PATH.
Users must be logged in to both platforms via their respective CLI tools
before using this script.

Usage:
  python cross_post.py "Text to post" [-i image_path]
  python cross_post.py -e [-i image_path]                  # Edit empty text in nano
  python cross_post.py -e "Initial text" [-i image_path]   # Edit initial text in nano
"""

import sys
import os
import subprocess
import shutil
import tempfile

# Flag file to indicate tools have been checked (stored in script directory)
FLAG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.tools_checked')

def check_tools():
    """Check for required CLI tools and create flag file if all are present."""
    # Skip check if flag file exists
    if os.path.exists(FLAG_FILE):
        return True
    
    # Check for required tools
    required_tools = ['bsky', 'toot', 'nano']
    missing_tools = []
    
    for tool in required_tools:
        if shutil.which(tool) is None:
            missing_tools.append(tool)
    
    if missing_tools:
        print(f"Error: Missing required tools: {', '.join(missing_tools)}")
        print("Please install these tools and ensure they are in your PATH.")
        return False
    
    # Verify tools are executable and working
    try:
        # Quick check that they respond to help/version
        subprocess.run(['bsky', '--help'], capture_output=True, check=True)
        subprocess.run(['toot', '--help'], capture_output=True, check=True)
        # For nano, run it with a flag that causes it to exit quickly with an error (to avoid hanging)
        subprocess.run(['nano', '-c'], input='', capture_output=True, timeout=2)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"Error: Tool verification failed: {e}")
        return False
    
    # Create flag file to skip future checks
    try:
        with open(FLAG_FILE, 'w') as f:
            f.write('Tools verified\n')
    except IOError as e:
        print(f"Warning: Could not create flag file: {e}")
        # Continue anyway - check will run again next time
    
    return True

def is_valid_image(filepath):
    """Check if a file is a valid image by inspecting its magic bytes."""
    signatures = {
        b'\x89PNG\r\n\x1a\n': 'PNG',
        b'\xff\xd8\xff':      'JPEG',
        b'GIF87a':            'GIF',
        b'GIF89a':            'GIF',
        b'RIFF':              'WebP',
        b'BM':                'BMP',
        b'II\x2a\x00':        'TIFF (little-endian)',
        b'MM\x00\x2a':        'TIFF (big-endian)',
    }
    try:
        with open(filepath, 'rb') as f:
            header = f.read(12)
        for magic, fmt in signatures.items():
            if header.startswith(magic):
                # Additional check for WebP (must contain 'WEBP' at offset 8)
                if fmt == 'WebP' and header[8:12] != b'WEBP':
                    continue
                return True
        return False
    except IOError:
        return False

def get_text_via_nano(initial_text=""):
    """Open nano editor to edit text and return the result."""
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt') as tmp_file:
        tmp_filename = tmp_file.name
        # Write initial text if provided
        if initial_text:
            tmp_file.write(initial_text)
    
    try:
        # Open nano editor
        result = subprocess.run(['nano', tmp_filename], 
                              capture_output=False,  # Let nano take over terminal
                              text=True)
        
        # Check if nano exited successfully
        if result.returncode != 0:
            print(f"Nano exited with code {result.returncode}")
            # Still try to read the file - user may have saved before exiting with error
        
        # Read the edited content
        with open(tmp_filename, 'r') as f:
            content = f.read()
        
        return content
    finally:
        # Clean up temporary file
        try:
            os.unlink(tmp_filename)
        except OSError:
            pass  # Ignore cleanup errors

def post_to_bluesky(text, image_path=None):
    """Post text to Bluesky using bsky CLI."""
    cmd = ['bsky', 'post']
    cmd.append(text)  # Text must come before options for bsky
    if image_path:
        cmd.extend(['--image', image_path])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("Bluesky: Post successful")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Bluesky: Post failed: {e.stderr.strip()}")
        return False
    except FileNotFoundError:
        print("Bluesky: Error - bsky command not found")
        return False

def post_to_mastodon(text, image_path=None):
    """Post text to Mastodon using toot CLI."""
    cmd = ['toot', 'post', '--visibility', 'public']
    if image_path:
        cmd.extend(['--media', image_path])
    cmd.append(text)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("Mastodon: Post successful")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Mastodon: Post failed: {e.stderr.strip()}")
        return False
    except FileNotFoundError:
        print("Mastodon: Error - toot command not found")
        return False

def main():
    """Main script execution."""
    # Check for help flag first
    if '-h' in sys.argv or '--help' in sys.argv:
        print(__doc__)
        sys.exit(0)
    
    # First, check for required tools (one-time check)
    if not check_tools():
        sys.exit(1)
    
    # Parse command line arguments
    edit_mode = False
    initial_text = ""
    image_path = None
    
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg in ['-e', '--edit']:
            edit_mode = True
        elif arg in ['-i', '--image']:
            i += 1
            if i >= len(sys.argv):
                print("Error: -i/--image requires a path argument")
                sys.exit(1)
            image_path = sys.argv[i]
        elif arg.startswith('-'):
            print(f"Error: Unknown option: {arg}")
            sys.exit(1)
        else:
            # This is a text argument
            if initial_text:
                print("Error: Only one text argument is allowed")
                sys.exit(1)
            initial_text = arg
        i += 1
    
    # Validate arguments
    if not edit_mode and not initial_text:
        print("Error: Text is required when not using edit mode")
        sys.exit(1)
    
    # Validate image path if provided
    if image_path:
        if not os.path.isfile(image_path):
            print(f"Error: Image file not found: {image_path}")
            sys.exit(1)
        if not is_valid_image(image_path):
            print(f"Error: File is not a valid image: {image_path}")
            print("Supported formats: PNG, JPEG, GIF, WebP, BMP, TIFF")
            sys.exit(1)
    
    # Get text to post (either from argument or via nano)
    if edit_mode:
        print("Opening nano for editing... (Save and exit to post)")
        text_to_post = get_text_via_nano(initial_text)
        # Check if user canceled or left empty
        if not text_to_post.strip():
            print("Error: No text to post after editing")
            sys.exit(1)
    else:
        text_to_post = initial_text
    
    # Post to both platforms
    bluesky_success = post_to_bluesky(text_to_post, image_path)
    mastodon_success = post_to_mastodon(text_to_post, image_path)
    
    # Summary
    if bluesky_success and mastodon_success:
        print("\nSuccessfully posted to both platforms!")
        sys.exit(0)
    elif bluesky_success:
        print("\nPosted to Bluesky only (Mastodon failed)")
        sys.exit(1)
    elif mastodon_success:
        print("\nPosted to Mastodon only (Bluesky failed)")
        sys.exit(1)
    else:
        print("\nFailed to post to either platform")
        sys.exit(1)

if __name__ == "__main__":
    main()
