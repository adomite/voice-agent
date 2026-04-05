from livekit.agents import AgentSession, Agent
from livekit.plugins.openai import OpenAIPlugin

agent = Agent(
    instructions="You are a helpful voice assistant."
)

session = AgentSession(
    agent=agent,
    plugins=[OpenAIPlugin()]
)

session.run()