from typing import Type
from pydantic import BaseModel, Field

class BaseTool:
    """
    A lightweight replacement for crewai.tools.BaseTool for native tool calling.
    Agent wrappers will directly invoke the `_run` method of descendants.
    """
    name: str = "base_tool"
    description: str = "Base description"
    args_schema: Type[BaseModel] = BaseModel

    def _run(self, **kwargs) -> str:
        raise NotImplementedError("Subclasses must implement _run")
