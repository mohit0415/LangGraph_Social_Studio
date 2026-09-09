from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from configs.database import connect
from configs.logger import get_logger
from src.node.accept_node import accept_node
from src.node.consistency_node import consistency_node
from src.node.manager_node import manager_node
from src.node.self_check_node import self_check_node
from src.node.writer_node import write_node
from src.routes.routing import MAX_ATTEMPTS, after_self_check, fan_out
from src.schemas.state import PlatformOutput, PlatformState, State

logger = get_logger(__name__)

__all__ = ["build_graph", "build_checkpointer", "MAX_ATTEMPTS"]


def build_checkpointer() -> SqliteSaver:
    saver = SqliteSaver(connect("checkpointer"))
    saver.setup()
    logger.info("checkpointer ready: SqliteSaver (graph state survives restarts)")
    return saver


def build_platform_graph():
    logger.debug(
        "compiling platform subgraph: write -> self_check -> {revise|accept} "
        "(max %d attempts per platform)",
        MAX_ATTEMPTS,
    )
    g = StateGraph(PlatformState, output_schema=PlatformOutput)

    g.add_node("write", write_node)
    g.add_node("self_check", self_check_node)
    g.add_node("accept", accept_node)

    g.add_edge(START, "write")
    g.add_edge("write", "self_check")
    g.add_conditional_edges(
        "self_check", after_self_check,
        {"revise": "write", "accept": "accept"},
    )
    g.add_edge("accept", END)

    compiled = g.compile()
    print(compiled.get_graph().draw_mermaid())
    logger.debug("platform subgraph compiled")
    return compiled


def build_graph(checkpointer=None):
    logger.info("building workflow graph: manager -> platform (parallel) -> consistency")
    g = StateGraph(State)

    g.add_node("manager", manager_node)
    g.add_node("platform", build_platform_graph())
    g.add_node("consistency", consistency_node)

    g.add_edge(START, "manager")

    g.add_conditional_edges("manager", fan_out, ["platform"])

    g.add_edge("platform", "consistency")
    g.add_edge("consistency", END)

    saver = checkpointer if checkpointer is not None else build_checkpointer()
    compiled = g.compile(checkpointer=saver)

    logger.info(
        "workflow graph compiled | checkpointer=%s (thread state is %s)",
        type(saver).__name__,
        "in-process only, lost on restart" if isinstance(saver, MemorySaver) else "persistent on disk",
    )
    return compiled
