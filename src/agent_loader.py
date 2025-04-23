import yaml
from crewai import Agent
from langchain_ollama import OllamaLLM

def load_llm(model_name="ollama/llama3.2", base_url="http://localhost:11434"):
    """Create and return an LLM instance."""
    try:
        return OllamaLLM(model=model_name, base_url=base_url)
    except Exception as e:
        print(f"Error connecting to Ollama at {base_url}: {e}")
        print("Please make sure Ollama is running and accessible.")
        exit(1)

def load_agents_config(config_path="config/agents.yaml"):
    """Load agent configurations from YAML file."""
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

def create_agents(llm=None):
    """Create agent instances from configuration."""
    if llm is None:
        llm = load_llm()
    
    agents_config = load_agents_config()
    agents = {}
    
    for agent_id, config in agents_config.items():
        agents[agent_id] = Agent(
            role=config['role'],
            goal=config['goal'],
            backstory=config['backstory'],
            llm=llm,
            allow_delegation=config.get('allow_delegation', False),
            verbose=config.get('verbose', True),
            tools=config.get('tools', [])
        )
    
    return agents