#!/usr/bin/env python3
import sys
import os

# # --- Debug --- 
# print(f"--- Python Executable: {sys.executable}", file=sys.stderr)
# print(f"--- Python sys.path: {sys.path}", file=sys.stderr)
# print(f"--- VIRTUAL_ENV env var: {os.getenv('VIRTUAL_ENV')}", file=sys.stderr)
# print(f"--- Current Working Dir: {os.getcwd()}", file=sys.stderr)
# # --- End Debug ---

import json
import argparse
from typing import Optional
import base64
from PIL import Image, ImageDraw
import requests
import io
import time
from io import BytesIO
import datetime

class FluxAPI:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("BFL_API_KEY")
        if not self.api_key:
            raise ValueError("API key must be provided or set in BFL_API_KEY environment variable")
        self.base_url = "https://api.bfl.ml"
        self.headers = {"X-Key": self.api_key}
    
    def encode_image(self, image_path: str) -> str:
        """Convert an image file to base64 string."""
        with open(image_path, 'rb') as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def save_image_from_url(self, url: str, filename: str, target_width: int = None, target_height: int = None) -> bool:
        """Download and save image from URL."""
        try:
            response = requests.get(url)
            response.raise_for_status()
            
            # Save the original image
            with open(filename, 'wb') as f:
                f.write(response.content)
            
            # If target dimensions are specified, resize the image
            if target_width and target_height:
                with Image.open(filename) as img:
                    # Resize image maintaining aspect ratio
                    img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                    # Save resized image
                    img.save(filename, quality=95)
            
            print(f"✨ Saved as {filename}")
            return True
        except Exception as e:
            print(f"Failed to save image: {str(e)}")
            return False
    
    def get_task_result(self, task_id: str, silent: bool = False) -> Optional[dict]:
        """Poll for task result."""
        max_attempts = 30
        attempt = 0
        
        print("Processing image...", file=sys.stderr)
        while attempt < max_attempts:
            if not silent:
                print(f"Processing image... (attempt {attempt + 1}/{max_attempts})", file=sys.stderr)
            
            response = requests.get(f"{self.base_url}/v1/get_result", params={'id': task_id})
            result = response.json()
            
            if result['status'] == 'Ready':
                return result
            elif result['status'] == 'failed':
                print(f"Task failed: {result.get('error', 'Unknown error')}", file=sys.stderr)
                return None
            
            attempt += 1
            time.sleep(2)
        
        print("Timeout waiting for result", file=sys.stderr)
        return None

    def generate_image(self, prompt: str, model: str = "flux.1.1-pro", width: int = None, height: int = None, aspect_ratio: str = None) -> Optional[str]:
        """Generate an image using any FLUX model."""
        endpoint = {
            "flux.1.1-pro": "/v1/flux-pro-1.1",
            "flux.1-pro": "/v1/flux-pro",
            "flux.1-dev": "/v1/flux-dev",
            "flux.1.1-ultra": "/v1/flux-pro-1.1-ultra",
        }.get(model)
        
        if not endpoint:
            raise ValueError(f"Unknown model: {model}")
        
        # Set default dimensions based on aspect ratio if provided
        if aspect_ratio:
            if aspect_ratio == '1:1':
                width, height = 1024, 1024
            elif aspect_ratio == '4:3':
                width, height = 1024, 768
            elif aspect_ratio == '3:4':
                width, height = 768, 1024
            elif aspect_ratio == '16:9':
                width, height = 1024, 576
            elif aspect_ratio == '9:16':
                width, height = 576, 1024
        else:
            # Use defaults if neither aspect ratio nor dimensions are provided
            width = width or 1024
            height = height or 768
        
        payload = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "aspect_ratio": aspect_ratio if aspect_ratio else None
        }
        response = requests.post(
            f"{self.base_url}{endpoint}",
            json=payload,
            headers=self.headers
        )
        
        task_id = response.json().get('id')
        if not task_id:
            print("Failed to start generation task", file=sys.stderr)
            return None
            
        result = self.get_task_result(task_id)
        if result and result.get('result', {}).get('sample'):
            return result['result']['sample']
        return None

    def create_mask(self, size: tuple, shape: str = 'rectangle', position: str = 'center') -> Image:
        """Create a mask for inpainting."""
        mask = Image.new('L', size, 0)
        draw = ImageDraw.Draw(mask)
        
        width, height = size
        
        if position == 'ground':
            horizon_y = height * 0.65
            y_start = horizon_y - (height * 0.05)
            points = [
                (0, y_start),
                (0, height),
                (width, height),
                (width, y_start)
            ]
            draw.polygon(points, fill=255)
        else:
            x1 = width * 0.25
            y1 = height * 0.25
            x2 = width * 0.75
            y2 = height * 0.75
            
            if shape == 'rectangle':
                draw.rectangle([x1, y1, x2, y2], fill=255)
            else:  # circle
                center = (width // 2, height // 2)
                radius = min(width, height) // 4
                draw.ellipse([center[0] - radius, center[1] - radius,
                             center[0] + radius, center[1] + radius], fill=255)
        
        return mask

    def inpaint(self, image_path: str, prompt: str, mask_shape: str = 'circle', position: str = 'center') -> Optional[str]:
        """Inpaint an image using a mask."""
        base_image = Image.open(image_path)
        mask = self.create_mask(base_image.size, shape=mask_shape, position=position)
        
        mask_path = 'temp_mask.jpg'
        mask.save(mask_path)
        
        payload = {
            "image": self.encode_image(image_path),
            "mask": self.encode_image(mask_path),
            "prompt": prompt,
            "steps": 50,
            "guidance": 60,
            "output_format": "jpeg",
            "safety_tolerance": 2
        }
        
        response = requests.post(
            f"{self.base_url}/v1/flux-pro-1.0-fill",
            json=payload,
            headers=self.headers
        )
        
        os.remove(mask_path)
        
        task_id = response.json().get('id')
        if not task_id:
            print("Failed to start inpaint task", file=sys.stderr)
            return None
            
        result = self.get_task_result(task_id)
        if result and result.get('result', {}).get('sample'):
            return result['result']['sample']
        return None

    def control_generate(self, control_type: str, control_image: str, prompt: str, **kwargs) -> Optional[str]:
        """Generate an image using any supported control type."""
        endpoints = {
            'canny': '/v1/flux-pro-1.0-canny',
            'depth': '/v1/flux-pro-1.0-depth',
            'pose': '/v1/flux-pro-1.0-pose'
        }
        
        default_params = {
            'canny': {'guidance': 30},
            'depth': {'guidance': 15},
            'pose': {'guidance': 25}
        }
        
        if control_type not in endpoints:
            raise ValueError(f"Unsupported control type: {control_type}")
            
        payload = {
            "prompt": prompt,
            "control_image": self.encode_image(control_image),
            "steps": kwargs.get('steps', 50),
            "output_format": kwargs.get('output_format', 'jpeg'),
            "safety_tolerance": kwargs.get('safety_tolerance', 2)
        }
        
        payload.update(default_params.get(control_type, {}))
        payload.update(kwargs)
        
        response = requests.post(
            f"{self.base_url}{endpoints[control_type]}",
            json=payload,
            headers=self.headers
        )
        
        task_id = response.json().get('id')
        if not task_id:
            print(f"Failed to start control ({control_type}) task", file=sys.stderr)
            return None
            
        result = self.get_task_result(task_id)
        if result and result.get('result', {}).get('sample'):
            return result['result']['sample']
        return None

    def img2img(self, image_path: str, prompt: str, model: str = "flux.1.1-pro", strength: float = 0.75, width: int = None, height: int = None) -> Optional[str]:
        """Generate an image using another image as reference"""
        endpoint = {
            "flux.1.1-pro": "/v1/flux-pro-1.1",
            "flux.1-pro": "/v1/flux-pro",
            "flux.1-dev": "/v1/flux-dev",
            "flux.1.1-ultra": "/v1/flux-pro-1.1-ultra",
        }.get(model)
        
        if not endpoint:
            raise ValueError(f"Unknown model: {model}")
            
        with Image.open(image_path) as img:
            orig_width, orig_height = img.size
            
            if width is None or height is None:
                width, height = orig_width, orig_height
            
            aspect_ratio = orig_height / orig_width
            
            total_pixels = width * height
            if total_pixels > 1048576:
                max_area = 1048576
                width = int((max_area / aspect_ratio) ** 0.5)
                height = int(width * aspect_ratio)
            
            buffered = BytesIO()
            img.save(buffered, format="JPEG", quality=95)
            image_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

        payload = {
            "prompt": prompt,
            "image": image_base64,
            "strength": strength,
            "width": width,
            "height": height,
            "guidance_scale": 7.5,
            "num_inference_steps": 50,
            "scheduler": "euler_ancestral",
            "preserve_init_image_color_profile": True
        }
        
        response = requests.post(
            f"{self.base_url}{endpoint}",
            headers=self.headers,
            json=payload
        )
        
        task_id = response.json().get('id')
        if not task_id:
            print("Failed to start image-to-image task", file=sys.stderr)
            return None
            
        result = self.get_task_result(task_id)
        if result and result.get('result', {}).get('sample'):
            return result['result']['sample']
        return None

# Function to fetch image and return format/data or save to file
def handle_image_url(image_url: str, output_path: Optional[str] = None, fetch_base64: bool = False, to_webp: bool = False):
    try:
        response = requests.get(image_url, stream=True)
        response.raise_for_status()

        content_type = response.headers.get('content-type', 'image/jpeg')
        original_format = content_type.split('/')[-1].lower() # e.g., jpeg, png
        # Ensure Pillow supports the format, default to jpeg if unknown/unsupported by Pillow for basic saving
        # Pillow generally uses file extensions for saving, but we need format for base64.
        save_format = original_format if original_format in ['png', 'gif'] else 'jpeg'

        image_bytes = response.content

        # --- WebP Conversion Logic ---
        final_format = save_format
        final_image_bytes = image_bytes
        
        if to_webp and (output_path or fetch_base64):
            try:
                img = Image.open(BytesIO(image_bytes))
                
                # Use RGBA for PNG source to preserve transparency, RGB otherwise
                if img.mode == 'P' or (save_format == 'png' and 'A' in img.mode): 
                     img = img.convert('RGBA')
                else:
                    img = img.convert('RGB') # Convert to RGB for WEBP saving

                output_buffer = BytesIO()
                img.save(output_buffer, format='WEBP', quality=90) # Changed quality to 90
                final_image_bytes = output_buffer.getvalue()
                final_format = 'webp'
            except Exception as convert_err:
                print(f"Warning: Failed to convert image to WebP: {convert_err}. Serving original format.", file=sys.stderr)
                # Fallback to original bytes and format if conversion fails
                final_format = save_format
                final_image_bytes = image_bytes
        # --- End WebP Conversion ---

        if output_path:
            # Adjust output path extension if converted to WebP
            if final_format == 'webp':
                base, _ = os.path.splitext(output_path)
                output_path = base + '.webp'
            
            abs_output_path = os.path.abspath(output_path)
            os.makedirs(os.path.dirname(abs_output_path), exist_ok=True)
            with open(abs_output_path, 'wb') as f:
                f.write(final_image_bytes) # Write final (potentially converted) bytes
            return json.dumps({"status": "saved", "path": abs_output_path})
        
        elif fetch_base64:
            base64_data = base64.b64encode(final_image_bytes).decode('utf-8')
            return json.dumps({"status": "success", "format": final_format, "data": base64_data})
        
        else: # Return URL
            # URL doesn't change even if conversion *could* happen later
            return json.dumps({"status": "success", "url": image_url})

    except requests.exceptions.RequestException as e:
        print(f"Error fetching image from URL {image_url}: {e}", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"Error saving image to {output_path}: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    # Main parser
    parser = argparse.ArgumentParser(description="FLUX CLI - Image Generation Tool")
    
    # Arguments applicable before subcommands (if any were needed)
    # parser.add_argument('--global-option', help='An option for all commands')

    subparsers = parser.add_subparsers(dest='command', help='Commands', required=True)

    # --- Base arguments for commands that produce an image ---
    base_image_parser = argparse.ArgumentParser(add_help=False)
    output_group = base_image_parser.add_mutually_exclusive_group()
    output_group.add_argument('--output', '-o', help='Absolute path to save the generated image file.')
    output_group.add_argument('--fetch-base64', action='store_true', help='Fetch image from URL and return base64 data instead of URL.')
    base_image_parser.add_argument('--to-webp', action='store_true', help='Convert the final image to WebP format (quality 85).')


    # --- Generate command ---
    generate_parser = subparsers.add_parser('generate', help='Generate an image from a text prompt', parents=[base_image_parser])
    generate_parser.add_argument('--prompt', '-p', required=True, help='Text prompt for image generation')
    generate_parser.add_argument('--model', '-m', choices=['flux.1.1-pro', 'flux.1-pro', 'flux.1-dev', 'flux.1.1-ultra'], default='flux.1.1-pro', help='Model to use for generation')
    generate_parser.add_argument('--aspect-ratio', '-ar', choices=['1:1', '4:3', '3:4', '16:9', '9:16'], help='Aspect ratio of the output image')
    generate_parser.add_argument('--width', '-w', type=int, help='Image width (ignored if aspect-ratio is set)')
    generate_parser.add_argument('--height', type=int, help='Image height (ignored if aspect-ratio is set)')


    # --- Img2Img command ---
    img2img_parser = subparsers.add_parser('img2img', help='Generate an image using another image as reference', parents=[base_image_parser])
    img2img_parser.add_argument('--image', required=True, help='Input image path')
    img2img_parser.add_argument('--prompt', '-p', required=True, help='Text prompt for generation')
    img2img_parser.add_argument('--name', required=True, help='Name for the generation')
    img2img_parser.add_argument('--model', '-m', choices=['flux.1.1-pro', 'flux.1-pro', 'flux.1-dev', 'flux.1.1-ultra'], default='flux.1.1-pro', help='Model to use for generation')
    img2img_parser.add_argument('--strength', type=float, default=0.85, help='Generation strength')
    img2img_parser.add_argument('--width', '-w', type=int, help='Output image width')
    img2img_parser.add_argument('--height', type=int, help='Output image height')


    # --- Inpaint command ---
    inpaint_parser = subparsers.add_parser('inpaint', help='Image inpainting', parents=[base_image_parser])
    inpaint_parser.add_argument('--image', required=True, help='Input image path')
    inpaint_parser.add_argument('--prompt', '-p', required=True, help='Text prompt for inpainting')
    inpaint_parser.add_argument('--mask-shape', choices=['circle', 'rectangle'], default='circle', help='Shape of the mask')
    inpaint_parser.add_argument('--position', choices=['center', 'ground'], default='center', help='Position of the mask')


    # --- Control command ---
    control_parser = subparsers.add_parser('control', help='ControlNet-like image generation', parents=[base_image_parser])
    control_parser.add_argument('--type', required=True, choices=['canny', 'depth', 'pose'], help='Type of control to use')
    control_parser.add_argument('--image', required=True, help='Input control image path')
    control_parser.add_argument('--prompt', '-p', required=True, help='Text prompt for generation')
    control_parser.add_argument('--steps', type=int, default=50, help='Number of inference steps')
    control_parser.add_argument('--guidance', type=float, help='Guidance scale')


    args = parser.parse_args()
    image_url = None # Variable to store the URL from the API call

    try:
        api = FluxAPI() # Assumes BFL_API_KEY is handled within FluxAPI or env vars

        if args.command == 'generate':
            image_url = api.generate_image(
                prompt=args.prompt,
                model=args.model,
                aspect_ratio=args.aspect_ratio,
                width=args.width,
                height=args.height
            )
        elif args.command == 'img2img':
             image_url = api.img2img(
                 image_path=args.image,
                 prompt=args.prompt,
                 name=args.name,
                 model=args.model,
                 strength=args.strength,
                 width=args.width,
                 height=args.height
             )
        elif args.command == 'inpaint':
             image_url = api.inpaint(
                 image_path=args.image,
                 prompt=args.prompt,
                 mask_shape=args.mask_shape,
                 position=args.position
             )
        elif args.command == 'control':
             image_url = api.control_generate(
                 type=args.type,
                 image_path=args.image,
                 prompt=args.prompt,
                 steps=args.steps,
                 guidance=args.guidance
             )
        # Add other command logic here if necessary

        if image_url:
            # Pass result to handler function, including the new to_webp flag
            result_json = handle_image_url(image_url, args.output, args.fetch_base64, args.to_webp)
            print(result_json) # Print the JSON result to stdout
        else:
            print(f"Error: Command '{args.command}' did not produce an image URL.", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error during API call or processing: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
