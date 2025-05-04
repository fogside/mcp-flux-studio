#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ErrorCode,
  ListToolsRequestSchema,
  McpError,
} from "@modelcontextprotocol/sdk/types.js";
import { spawn } from "child_process";
import { z } from "zod";
import * as fs from "fs";
import * as path from "path";

class FluxServer {
  private server: McpServer;
  private fluxPath: string;

  constructor() {
    this.server = new McpServer({
      name: "flux-server",
      version: "0.1.0",
    });
    this.fluxPath = process.env.FLUX_PATH || "";
    if (!this.fluxPath) {
      throw new Error(
        "FLUX_PATH environment variable must be set to the directory containing fluxcli.py"
      );
    }
    if (!process.env.BFL_API_KEY) {
      throw new Error(
        "BFL_API_KEY environment variable must be set for the Flux API"
      );
    }
    this.setupToolHandlers();
    process.on("SIGINT", async () => {
      await this.server.close();
      process.exit(0);
    });
  }

  async runPythonCommand(args: string[]) {
    return new Promise((resolve, reject) => {
      // const pythonPath =
      //   "/Users/zenja/Projects/mcp-servers/mcp-flux-studio/.venv/bin/python"; // Removed hardcoded path
      const pythonPath = process.env.VIRTUAL_ENV
        ? `${process.env.VIRTUAL_ENV}/bin/python`
        : "python3"; // Reverted to VIRTUAL_ENV check or fallback
      // console.log(`Using python path: ${pythonPath}`); // Keep debug logs removed
      // console.log(`Using cwd: ${this.fluxPath}`); // Keep debug logs removed

      const childProcess = spawn(pythonPath, ["fluxcli.py", ...args], {
        cwd: this.fluxPath,
        env: process.env,
      });

      let output = "";
      let errorOutput = "";

      childProcess.stdout?.on("data", (data) => {
        output += data.toString();
      });

      childProcess.stderr?.on("data", (data) => {
        errorOutput += data.toString();
      });

      childProcess.on("close", (code) => {
        if (code === 0) {
          // Try parsing the output as JSON
          try {
            const parsedOutput = JSON.parse(output);
            if (parsedOutput.data && parsedOutput.format) {
              resolve(parsedOutput); // Resolve with the parsed object
            } else {
              // If JSON doesn't have expected structure, reject
              console.warn(
                "Python script output was JSON but lacked format/data fields. Output:",
                output
              ); // Fixed console call
              reject(
                new Error(`Python script returned unexpected JSON: ${output}`)
              );
            }
          } catch (e) {
            // If output is not valid JSON, reject with an error
            console.error(
              "Python script output was not valid JSON. Output:",
              output
            ); // Fixed console call
            reject(
              new Error(`Python script returned non-JSON output: ${output}`)
            );
          }
        } else {
          // Include stderr in the rejection message for better debugging
          reject(
            new Error(`Flux command failed with code ${code}: ${errorOutput}`)
          );
        }
      });
    });
  }

  setupToolHandlers() {
    const generateSchema = z.object({
      prompt: z.string().describe("Text prompt for image generation"),
      model: z
        .enum(["flux.1.1-pro", "flux.1-pro", "flux.1-dev", "flux.1.1-ultra"])
        .default("flux.1.1-pro")
        .describe("Model to use for generation"),
      aspect_ratio: z
        .enum(["1:1", "4:3", "3:4", "16:9", "9:16"])
        .optional()
        .describe("Aspect ratio of the output image"),
      width: z
        .number()
        .optional()
        .describe("Image width (ignored if aspect-ratio is set)"),
      height: z
        .number()
        .optional()
        .describe("Image height (ignored if aspect-ratio is set)"),
    });
    this.server.tool(
      "generate",
      generateSchema.shape,
      async (args: z.infer<typeof generateSchema>) => {
        const cmdArgs = ["generate"];
        cmdArgs.push("--prompt", args.prompt);
        if (args.model) cmdArgs.push("--model", args.model);
        if (args.aspect_ratio)
          cmdArgs.push("--aspect-ratio", args.aspect_ratio);
        if (args.width) cmdArgs.push("--width", args.width.toString());
        if (args.height) cmdArgs.push("--height", args.height.toString());

        const result = (await this.runPythonCommand(cmdArgs)) as {
          format: string;
          data: string;
        };

        return {
          content: [
            {
              type: "image",
              mimeType: `image/${result.format}`,
              data: result.data,
            },
          ], // Use image type
        };
      }
    );

    const img2imgSchema = z.object({
      image: z.string().describe("Input image path"),
      prompt: z.string().describe("Text prompt for generation"),
      name: z.string().describe("Name for the generation"),
      model: z
        .enum(["flux.1.1-pro", "flux.1-pro", "flux.1-dev", "flux.1.1-ultra"])
        .default("flux.1.1-pro")
        .describe("Model to use for generation"),
      strength: z.number().default(0.85).describe("Generation strength"),
      width: z.number().optional().describe("Output image width"),
      height: z.number().optional().describe("Output image height"),
    });
    this.server.tool(
      "img2img",
      img2imgSchema.shape,
      async (args: z.infer<typeof img2imgSchema>) => {
        const cmdArgs = ["img2img"];
        cmdArgs.push("--image", args.image);
        cmdArgs.push("--prompt", args.prompt);
        cmdArgs.push("--name", args.name);
        if (args.model) cmdArgs.push("--model", args.model);
        if (args.strength) cmdArgs.push("--strength", args.strength.toString());
        if (args.width) cmdArgs.push("--width", args.width.toString());
        if (args.height) cmdArgs.push("--height", args.height.toString());

        const result = (await this.runPythonCommand(cmdArgs)) as {
          format: string;
          data: string;
        };
        return {
          content: [
            {
              type: "image",
              mimeType: `image/${result.format}`,
              data: result.data,
            },
          ], // Use image type
        };
      }
    );

    const inpaintSchema = z.object({
      image: z.string().describe("Input image path"),
      prompt: z.string().describe("Text prompt for inpainting"),
      mask_shape: z
        .enum(["circle", "rectangle"])
        .default("circle")
        .describe("Shape of the mask"),
      position: z
        .enum(["center", "ground"])
        .default("center")
        .describe("Position of the mask"),
    });
    this.server.tool(
      "inpaint",
      inpaintSchema.shape,
      async (args: z.infer<typeof inpaintSchema>) => {
        const cmdArgs = ["inpaint"];
        cmdArgs.push("--image", args.image);
        cmdArgs.push("--prompt", args.prompt);
        if (args.mask_shape) cmdArgs.push("--mask-shape", args.mask_shape);
        if (args.position) cmdArgs.push("--position", args.position);

        const result = (await this.runPythonCommand(cmdArgs)) as {
          format: string;
          data: string;
        };
        return {
          content: [
            {
              type: "image",
              mimeType: `image/${result.format}`,
              data: result.data,
            },
          ], // Use image type
        };
      }
    );

    const controlSchema = z.object({
      type: z
        .enum(["canny", "depth", "pose"])
        .describe("Type of control to use"),
      image: z.string().describe("Input control image path"),
      prompt: z.string().describe("Text prompt for generation"),
      steps: z.number().default(50).describe("Number of inference steps"),
      guidance: z.number().optional().describe("Guidance scale"),
    });
    this.server.tool(
      "control",
      controlSchema.shape,
      async (args: z.infer<typeof controlSchema>) => {
        const cmdArgs = ["control"];
        cmdArgs.push("--type", args.type);
        cmdArgs.push("--image", args.image);
        cmdArgs.push("--prompt", args.prompt);
        if (args.steps) cmdArgs.push("--steps", args.steps.toString());
        if (args.guidance) cmdArgs.push("--guidance", args.guidance.toString());

        const result = (await this.runPythonCommand(cmdArgs)) as {
          format: string;
          data: string;
        };
        return {
          content: [
            {
              type: "image",
              mimeType: `image/${result.format}`,
              data: result.data,
            },
          ], // Use image type
        };
      }
    );
  }

  async run() {
    const transport = new StdioServerTransport();
    transport.onclose = () => console.log("Transport closed");
    console.log("Starting Flux MCP Server...");
    await this.server.connect(transport);
    console.log("Flux MCP Server connected via stdio.");
  }
}

const server = new FluxServer();
server.run().catch((error: Error) => {
  console.error("Failed to start Flux MCP server:", error);
  process.exit(1);
});
