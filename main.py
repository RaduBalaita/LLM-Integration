import os
import subprocess
from typing import List, Dict
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import json

# Initialize FastAPI app
app = FastAPI()


# Define request/response models
class AgentRequest(BaseModel):
    msg: str


class AgentResponse(BaseModel):
    msg: str


# Configure API key
API_KEY = "AIzaSyD7dCuDYRHShR4qvVCuwMiqTSj227Q8eWo"


def query_llm(prompt: str) -> str:
    """Query the Google PaLM API."""
    url = "https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent"

    headers = {
        "Content-Type": "application/json"
    }

    data = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }]
    }

    try:
        response = requests.post(
            f"{url}?key={API_KEY}",
            headers=headers,
            json=data
        )

        if response.status_code == 200:
            response_data = response.json()
            if 'candidates' in response_data and len(response_data['candidates']) > 0:
                return response_data['candidates'][0]['content']['parts'][0]['text']
            else:
                raise HTTPException(status_code=500, detail="No response from LLM")
        else:
            print(f"API Response: {response.text}")  # Debug print
            raise HTTPException(
                status_code=response.status_code,
                detail=f"LLM API Error: {response.text}"
            )
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")

# [Previous helper functions remain the same...]
def list_files(directory: str = ".") -> str:
    """List all files in the specified directory."""
    try:
        cmd = f'dir /B "{directory}"' if os.name == 'nt' else f'ls -la "{directory}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error listing files: {e.stderr}"


def find_files(directory: str, pattern: str) -> str:
    """Find files matching a pattern in the directory."""
    try:
        if os.name == 'nt':
            cmd = f'dir /B /S "{directory}\\*{pattern}"'
        else:
            cmd = f'find "{directory}" -name "*{pattern}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error finding files: {e.stderr}"


def read_file(filepath: str) -> str:
    """Read contents of a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"


def rename_file(old_path: str, new_path: str) -> str:
    """Rename a file."""
    try:
        os.rename(old_path, new_path)
        return f"Successfully renamed {old_path} to {new_path}"
    except Exception as e:
        return f"Error renaming file: {str(e)}"


def search_in_file(filepath: str, pattern: str) -> str:
    """Search for a pattern in a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            return "true" if pattern.lower() in content.lower() else "false"
    except Exception as e:
        return f"Error searching file: {str(e)}"


async def process_file_task(task: str) -> str:
    """Process a file-related task."""
    system_context = """You are a file management assistant. Given a task, respond with specific commands to execute.
    Use only these commands:
    - list_files(directory)
    - find_files(directory, pattern)
    - read_file(filepath)
    - rename_file(old_path, new_path)
    - search_in_file(filepath, pattern)

    Respond with ONLY the commands to run, one per line. No explanations or other text."""

    full_prompt = f"{system_context}\n\nTask: {task}\n\nCommands:"

    try:
        # Get commands from LLM
        commands_text = query_llm(full_prompt)
        if not commands_text:
            return "No commands generated by LLM"

        # Execute commands and collect results
        results = []
        commands = [cmd.strip() for cmd in commands_text.split('\n') if cmd.strip()]

        for command in commands:
            if not any(command.startswith(prefix) for prefix in
                       ['list_files', 'find_files', 'read_file', 'rename_file', 'search_in_file']):
                continue

            try:
                # Safely evaluate the command
                if command.startswith('list_files'):
                    dir_path = eval(command.split('(')[1].rstrip(')'))
                    results.append(list_files(dir_path))
                elif command.startswith('find_files'):
                    args = eval(command.split('(')[1].rstrip(')'))
                    if isinstance(args, tuple):
                        results.append(find_files(*args))
                    else:
                        results.append(find_files(args, ""))
                elif command.startswith('read_file'):
                    filepath = eval(command.split('(')[1].rstrip(')'))
                    results.append(read_file(filepath))
                elif command.startswith('rename_file'):
                    args = eval(command.split('(')[1].rstrip(')'))
                    if isinstance(args, tuple):
                        results.append(rename_file(*args))
                elif command.startswith('search_in_file'):
                    args = eval(command.split('(')[1].rstrip(')'))
                    if isinstance(args, tuple):
                        results.append(search_in_file(*args))
            except Exception as e:
                results.append(f"Error executing {command}: {str(e)}")

        return "\n".join(results) if results else "No results from commands"

    except Exception as e:
        return f"Error processing task: {str(e)}"


@app.post("/agent")
async def process_request(request: AgentRequest) -> AgentResponse:
    """Process the agent request and return response."""
    try:
        result = await process_file_task(request.msg)
        return AgentResponse(msg=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def main():
    """Run the FastAPI server."""
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()