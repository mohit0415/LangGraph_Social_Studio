from typing import TypedDict,Annotated,Dict,List
import operator


class SocialMediaState(TypedDict):
    messages : Annotated[list,operator.add]
    thought_history : Annotated[List[str],operator.add]
    action_log : Annotated[List[Dict],operator.add]
    observation_results : Annotated[List[str],operator.add]
    task_completion : bool