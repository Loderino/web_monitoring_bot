from dataclasses import dataclass

from dataclasses_json import dataclass_json


@dataclass_json
@dataclass
class PanelButtonContent:
    my_monitors: str
    add_monitor: str
    settings: str
    statistics: str


@dataclass_json
@dataclass
class InlineButtonContent:
    insert_url: str
    select_interval: str
    cancel: str
    finish: str


@dataclass_json
@dataclass
class ButtonContent:
    inline: InlineButtonContent
    panel: PanelButtonContent


@dataclass_json
@dataclass
class Language:
    button: ButtonContent
    some_error: str
    not_defined: str
    successful_changes: str
    help_command_description: str
    monitors_command_description: str
    start_command_answer: str
    help_command_answer: str

    new_monitor_task_status: str
    new_monitor_task_success: str
    new_monitor_existing_url: str
    new_monitor_wrong_url: str
    update_monitor_success: str
    delete_monitor_success: str
    notifications_settings: str
