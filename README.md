# MCP Flux Studio

A Model Context Protocol (MCP) server that brings Flux's advanced image generation capabilities to Cursor.

_Note: This is a fork of the original [jmanhype/mcp-flux-studio](https://github.com/jmanhype/mcp-flux-studio) repository, adapted to resolve compatibility issues and ensure smooth operation within the Cursor environment._

## Features

Provides MCP tools for Cursor's AI assistant to:

- Generate images from text prompts (`generate`)
- Generate images based on existing images (`img2img`)
- Inpaint parts of an image (`inpaint`)
- Generate images using structural control like canny edges, depth maps, or poses (`control`)

## Installation and Usage (Cursor)

Follow these steps to install and configure the server for use with Cursor:

1.  **Prerequisites:**

    - [Node.js](https://nodejs.org/) (Version 18 or higher recommended)
    - [Python](https://www.python.org/) (Version 3.10 or higher recommended)
    - A Flux API key from [Black Forest Labs](https://flux.blackforestlabs.ai/)
    - [Cursor](https://cursor.sh/)

2.  **Clone the Repository:**
    Open your terminal and run:

    ```bash
    git clone https://github.com/fogside/mcp-flux-studio.git # Use this updated URL
    cd mcp-flux-studio
    ```

3.  **Set up Python Virtual Environment:**
    It's highly recommended to use a Python virtual environment to manage dependencies.

    ```bash
    # Navigate into the project directory if you aren't already there
    cd /path/to/mcp-flux-studio

    # Create the virtual environment
    python3 -m venv .venv

    # Activate the virtual environment
    # On macOS/Linux:
    source .venv/bin/activate
    # On Windows:
    # .venv\Scripts\activate
    ```

    You should see `(.venv)` preceding your terminal prompt.

4.  **Install Python Dependencies:**
    While the virtual environment is active, install the required Python packages:

    ```bash
    pip install -r src/cli/requirements.txt
    ```

5.  **Install Node.js Dependencies:**
    Install the necessary Node.js packages:

    ```bash
    npm install
    ```

6.  **Build the Project:**
    Compile the TypeScript code to JavaScript:

    ```bash
    npm run build
    ```

7.  **Configure Cursor MCP:**

    - Open the Command Palette in Cursor (Cmd+Shift+P or Ctrl+Shift+P).
    - Type "MCP" and select "MCP: Manage Custom Servers".
    - Click "Add Server".
    - Configure the server using the UI, or alternatively, you can manually edit your `mcp.json` file (usually located at `~/.cursor/mcp.json`). Here's an example snippet to add to the `servers` array in that file:

    ```json
    {
      "name": "Flux Studio", // Or your preferred name
      "command": "node",
      "args": [
        "/Users/YOUR_USERNAME/path/to/mcp-flux-studio/build/index.js" // <-- Replace with absolute path
      ],
      "enabled": true,
      "workingDirectory": "/Users/YOUR_USERNAME/path/to/mcp-flux-studio", // <-- Replace with absolute path
      "environment": {
        "BFL_API_KEY": "YOUR_API_KEY_HERE", // <-- Replace or ensure set elsewhere
        "FLUX_PATH": "/Users/YOUR_USERNAME/path/to/mcp-flux-studio/src/cli", // <-- Replace with absolute path
        "VIRTUAL_ENV": "/Users/YOUR_USERNAME/path/to/mcp-flux-studio/.venv" // <-- Add this line, replace with absolute path to the .venv folder
      }
    }
    ```

    - **Important Notes on Configuration:**
      - Replace `/Users/YOUR_USERNAME/path/to/mcp-flux-studio` with the actual **absolute path** to where you cloned the repository on your machine.
      - Replace `YOUR_API_KEY_HERE` with your actual Black Forest Labs API key. **Never commit your API key directly to Git.**
      - Ensure the `workingDirectory` points to the root of the cloned project.
      - Ensure `FLUX_PATH` points to the `src/cli` directory within the project.
      - Setting `VIRTUAL_ENV` to the absolute path of the `.venv` directory helps the server find the correct Python executable with the necessary dependencies.
    - Save the server configuration (either in the UI or by saving the `mcp.json` file).

8.  **Activate and Use:**
    - Ensure the server switch is enabled in the "MCP: Manage Custom Servers" menu.
    - You should now be able to ask Cursor's AI assistant to use the Flux tools (e.g., "generate an image of a futuristic cityscape using flux studio"). The tool names will likely start with `mcp_flux-studio_`.

## Basic Usage Examples

Once configured, you can ask Cursor's AI assistant to perform tasks like:

- `@flux-studio generate a photorealistic image of a cat wearing sunglasses`
- `@flux-studio inpaint the selected area of the image to add a small boat, prompt: 'small red boat'` (Assuming you have an image open and selected part of it)

_(Note: The exact invocation prefix like `@flux-studio` depends on the `name` you set for the server in Cursor's MCP settings)._

The AI assistant automatically discovers the available tools based on the server configuration. You can usually refer to the server by its name or describe the action you want it to perform. For more details on how Cursor interacts with MCP tools, see the official documentation:

- **Cursor MCP Documentation:** [https://docs.cursor.com/context/model-context-protocol](https://docs.cursor.com/context/model-context-protocol)
- **Using MCP Tools in Chat:** [https://docs.cursor.com/context/model-context-protocol#using-mcp-in-chat](https://docs.cursor.com/context/model-context-protocol#using-mcp-in-chat)

## License

MIT License

---

## Detailed Tool Usage Examples

Below are examples showing the expected JSON input format for each tool. Note that when using the tool via Cursor chat, you typically provide the information in natural language, and Cursor translates it into this format.

**Output Options:**

- Use `output_path` to save the image directly to an **absolute path** on the server machine. This returns a text confirmation.
- Use `return_format: "base64"` (default) to get the image data embedded in the response, displayed as an image in Cursor.
- Use `return_format: "url"` to get a URL for the generated image. This returns a text URL.
- Note: `output_path` takes precedence over `return_format`.

### `generate`

Generate an image from a text prompt.

```json
{
  "prompt": "A photorealistic cat",
  "model": "flux.1.1-pro", // Optional, defaults to flux.1.1-pro
  "aspect_ratio": "1:1", // Optional
  "width": 1024, // Optional
  "height": 1024, // Optional
  "output_path": "/path/to/save/cat.jpg", // Optional: Absolute path to save file
  "return_format": "base64" // Optional: "base64" or "url" (ignored if output_path is set)
}
```

### `img2img`

Generate an image using another image as reference.

```json
{
  "image": "input.jpg", // Required: Path to input image
  "prompt": "Convert to oil painting", // Required
  "name": "oil_painting", // Required: A name for the generation (used by API)
  "model": "flux.1.1-pro", // Optional
  "strength": 0.85, // Optional
  "width": 1024, // Optional
  "height": 1024, // Optional
  "output_path": "/path/to/save/oil.jpg", // Optional: Absolute path to save file
  "return_format": "base64" // Optional: "base64" or "url" (ignored if output_path is set)
}
```

### `inpaint`

Image inpainting.

```json
{
  "image": "input.jpg", // Required: Path to input image
  "prompt": "Add a hat on the person", // Required
  "mask_shape": "circle", // Optional: "circle" or "rectangle"
  "position": "center", // Optional: "center" or "ground"
  "output_path": "/path/to/save/inpainted.jpg", // Optional: Absolute path to save file
  "return_format": "base64" // Optional: "base64" or "url" (ignored if output_path is set)
}
```

### `control`

ControlNet-like image generation.

```json
{
  "type": "canny", // Required: "canny", "depth", or "pose"
  "image": "control_image.jpg", // Required: Path to control image
  "prompt": "Generate character based on pose", // Required
  "steps": 50, // Optional
  "guidance": 25, // Optional
  "output_path": "/path/to/save/controlled.jpg", // Optional: Absolute path to save file
  "return_format": "base64" // Optional: "base64" or "url" (ignored if output_path is set)
}
```
