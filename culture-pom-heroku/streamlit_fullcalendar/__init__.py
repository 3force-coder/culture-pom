import streamlit.components.v1 as components
import os

_component_func = components.declare_component(
    "fullcalendar",
    path=os.path.join(os.path.dirname(__file__), "frontend")
)

def fullcalendar(
    events=None,
    external_events=None,
    initial_date=None,
    locale='fr',
    editable=True,
    droppable=True,
    key=None
):
    component_value = _component_func(
        events=events or [],
        external_events=external_events or [],
        initial_date=initial_date,
        locale=locale,
        editable=editable,
        droppable=droppable,
        key=key,
        default=None
    )
    return component_value
