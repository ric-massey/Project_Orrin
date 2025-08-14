# state_graph.py

from typing import Callable, Dict, Tuple, Optional, Any

Context = Dict[str, Any]
NodeFn = Callable[[Context], Tuple[Optional[str], Context]]

class StateGraph:
    """Deterministic state graph driver.

    Each node is a function that takes `context` and returns `(next_node_name, context)`.
    To terminate, return `None` (or the sentinel "END").
    """

    def __init__(self) -> None:
        self.nodes: Dict[str, NodeFn] = {}
        self.start: str = ""

    def add_node(self, name: str, fn: NodeFn) -> None:
        if not callable(fn):
            raise TypeError(f"Node '{name}' must be callable")
        self.nodes[name] = fn

    def set_start(self, name: str) -> None:
        if name not in self.nodes:
            raise ValueError(f"Start node '{name}' not found in graph")
        self.start = name

    def run(self, context: Context, max_steps: int = 50) -> Dict[str, Any]:
        if not self.start:
            raise RuntimeError("Start node not set. Call set_start(name) first.")
        if self.start not in self.nodes:
            raise RuntimeError(f"Start node '{self.start}' is not in the graph.")

        cur = self.start
        steps = 0
        history: list[tuple[str, Optional[str]]] = []

        while cur and cur != "END" and steps < max_steps:
            fn = self.nodes.get(cur)
            if fn is None:
                # record and break on missing node
                history.append((cur, "__missing_node__"))
                break
            try:
                nxt, context = fn(context)
            except Exception as e:
                # record error and stop
                history.append((cur, f"__error__: {type(e).__name__}"))
                break

            history.append((cur, nxt))
            if nxt is None or nxt == "END":
                break
            if nxt not in self.nodes:
                # invalid transition; record and stop
                history.append((nxt, "__unknown_target__"))
                break

            cur = nxt
            steps += 1

        return {"history": history, "context": context, "steps": steps}