# Web Automation Agent

An AI-powered web automation system that uses Playwright and OpenAI GPT to automatically execute web tasks.

## Project Structure

```
.
├── agent.py           # Main entry point, coordinates all modules
├── config.py          # Website configuration management
├── dom_processor.py   # DOM extraction and simplification
├── ai_agent.py        # AI decision engine (OpenAI API)
├── web_actions.py     # Web action execution
└── dataset/           # Screenshot and debug file storage directory
```

## Module Description

### 1. agent.py - Main Program
- Program entry point
- Command-line argument parsing
- Coordinates the automation flow (Observe -> Think -> Act loop)
- Error handling and debugging features

### 2. config.py - Configuration Management
- `SITE_CONFIGS`: Stores site-specific configurations
- `get_site_config()`: Automatically detects website from URL and returns corresponding configuration
- Supported websites:
  - Trello
  - Linear
  - Notion
  - Easy to extend for new websites

### 3. dom_processor.py - DOM Processing
- `get_simplified_dom()`: Extracts and simplifies webpage DOM structure
- Smart context awareness:
  - Prioritizes modal dialogs
  - Detects popup menus
  - Filters invisible elements
- Assigns unique IDs to interactive elements

### 4. ai_agent.py - AI Decision Making
- `think()`: Calls OpenAI API for intelligent decision making
- Analyzes current DOM state
- Decides next action based on goal and history
- Returns structured action commands (click, type, done)

### 5. web_actions.py - Action Execution
- `act()`: Executes specific actions on webpage
- Supported actions:
  - Click elements
  - Type text
  - Task completion detection
- Automatic screenshot after each action

## Usage

### Environment Setup

1. Set OpenAI API key:
```bash
export OPENAI_API_KEY=sk-...
```

2. Run login script to generate authentication files (e.g., `trello_auth.json`)

### Running the Agent

```bash
# Use default goal
python agent.py --url "https://trello.com/b/YOUR_BOARD"

# Custom goal
python agent.py --url "https://linear.app/workspace/..." --goal "Create a new issue"

# Specify task name (for screenshot storage)
python agent.py --url "..." --task-name "my_custom_task"
```

## Features

- **Multi-site Support**: Easy configuration for new websites
- **Intelligent Decision Making**: Uses GPT-4 for dynamic decision making
- **Smart DOM Processing**: Automatic recognition of modals and menus
- **Debug Friendly**: Automatic screenshots for each step
- **Error Recovery**: Detailed error logs and DOM dumps
- **Action History**: Maintains complete operation records

## Dependencies

- `playwright`: Browser automation
- `openai`: OpenAI API client

## Extending to New Websites

Add new configuration in `SITE_CONFIGS` in `config.py`:

```python
"your_site": {
    "auth_file": "your_site_auth.json",
    "anchor_selector": "selector",
    "default_goal": "default task goal",
    "site_context_prompt": "site context description"
}
```

Then add URL detection logic in the `get_site_config()` function.

## Debugging

Debug files are saved in `dataset/[task_name]/` directory:
- Screenshots for each step
- HTML dumps on error
- Simplified DOM structure
- Error state screenshots